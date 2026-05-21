<?php

declare(strict_types=1);

use App\KeycloakClient;
use App\SessionManager;
use App\TokenEncryptor;
use Predis\Client as RedisClient;
use Psr\Http\Message\ResponseInterface as Response;
use Psr\Http\Message\ServerRequestInterface as Request;
use Slim\Factory\AppFactory;

require __DIR__ . '/../vendor/autoload.php';

// ── Загрузка переменных окружения ──────────────────────────────────────────
$dotenv = Dotenv\Dotenv::createImmutable(__DIR__ . '/..');
$dotenv->safeLoad();

// ── DI: создание зависимостей ───────────────────────────────────────────────
$redis = new RedisClient([
    'scheme' => 'tcp',
    'host'   => $_ENV['REDIS_HOST'] ?? 'redis',
    'port'   => (int) ($_ENV['REDIS_PORT'] ?? 6379),
]);

$encryptor      = new TokenEncryptor();
$sessionManager = new SessionManager($redis, $encryptor);
$keycloak       = new KeycloakClient();

// ── Slim App ────────────────────────────────────────────────────────────────
$app = AppFactory::create();
$app->addErrorMiddleware(true, true, true);
$app->addBodyParsingMiddleware();

$frontendUrl = rtrim($_ENV['FRONTEND_URL'] ?? 'http://localhost:3000', '/');
$cookieName  = 'bionicpro_session';
$cookieTtl   = (int) ($_ENV['SESSION_TTL'] ?? 1800);

// ── CORS ──────────────────────────────────────────────────────────────────────
$app->add(function (Request $request, $handler) use ($frontendUrl): Response {
    $response = $handler->handle($request);
    return $response
        ->withHeader('Access-Control-Allow-Origin', $frontendUrl)
        ->withHeader('Access-Control-Allow-Credentials', 'true')
        ->withHeader('Access-Control-Allow-Headers', 'Content-Type')
        ->withHeader('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS');
});

$app->options('/{routes:.+}', function (Request $request, Response $response): Response {
    return $response->withStatus(200);
});

// ─────────────────────────────────────────────────────────────────────────────
// GET /auth/login
//
// Шаг 1 BFF-потока: генерирует PKCE-параметры на бэкенде,
// сохраняет code_verifier в Redis и возвращает URL авторизации Keycloak.
// Фронтенд перенаправляет пользователя на этот URL.
// ─────────────────────────────────────────────────────────────────────────────
$app->get('/auth/login', function (Request $request, Response $response) use ($sessionManager, $keycloak): Response {
    $pkce = $sessionManager->initiatePkceFlow($keycloak);

    $response->getBody()->write(json_encode([
        'authorization_url' => $pkce['authorization_url'],
    ]));

    return $response->withHeader('Content-Type', 'application/json');
});

// ─────────────────────────────────────────────────────────────────────────────
// POST /auth/callback
//
// Шаг 2 BFF-потока: фронтенд отправляет {code, state} после редиректа
// от Keycloak. Бэкенд достаёт code_verifier из Redis по state,
// обменивает code на токены, сохраняет их и возвращает HttpOnly-cookie.
// ─────────────────────────────────────────────────────────────────────────────
$app->post('/auth/callback', function (Request $request, Response $response) use (
    $sessionManager, $keycloak, $cookieName, $cookieTtl
): Response {
    $body         = (array) $request->getParsedBody();
    $code         = $body['code']          ?? '';
    $state        = $body['state']         ?? '';
    $codeVerifier = $body['code_verifier'] ?? '';

    if ($code === '') {
        $response->getBody()->write(json_encode(['error' => 'Missing code']));
        return $response->withStatus(400)->withHeader('Content-Type', 'application/json');
    }

    // Если библиотека прислала code_verifier напрямую — используем его.
    // Иначе достаём из Redis по state (BFF-инициированный flow через /auth/login).
    if ($codeVerifier === '' && $state !== '') {
        $codeVerifier = $sessionManager->consumeCodeVerifier($state) ?? '';
    }

    if ($codeVerifier === '') {
        $response->getBody()->write(json_encode(['error' => 'Missing code_verifier']));
        return $response->withStatus(400)->withHeader('Content-Type', 'application/json');
    }

    try {
        // Обмен code на токены — выполняется ТОЛЬКО на бэкенде
        $tokens = $keycloak->exchangeCode($code, $codeVerifier);
    } catch (\RuntimeException $e) {
        $response->getBody()->write(json_encode(['error' => 'Token exchange failed']));
        return $response->withStatus(502)->withHeader('Content-Type', 'application/json');
    }

    // Сохраняем access_token в Redis (plaintext),
    // refresh_token в Redis (AES-256-GCM зашифрован)
    $sessionId = $sessionManager->createSession(
        $tokens['access_token'],
        $tokens['refresh_token']
    );

    // Возвращаем сессионную cookie с флагами HttpOnly + SameSite=Lax
    // Secure=true добавляется в продакшн через HTTPS; для dev отключено
    $cookieValue = "{$cookieName}={$sessionId}; Path=/; HttpOnly; SameSite=Lax; Max-Age={$cookieTtl}";

    $response->getBody()->write(json_encode(['ok' => true]));
    return $response
        ->withStatus(200)
        ->withHeader('Content-Type', 'application/json')
        ->withHeader('Set-Cookie', $cookieValue);
});

// ─────────────────────────────────────────────────────────────────────────────
// GET /auth/me
//
// Проверяет сессионную cookie, при необходимости обновляет access_token
// через refresh_token, выполняет ротацию сессии и возвращает user info.
// ─────────────────────────────────────────────────────────────────────────────
$app->get('/auth/me', function (Request $request, Response $response) use (
    $sessionManager, $keycloak, $cookieName, $cookieTtl
): Response {
    [$sessionId, $tokens, $errorResponse] = resolveSession(
        $request, $response, $sessionManager, $keycloak, $cookieName
    );

    if ($errorResponse !== null) {
        return $errorResponse;
    }

    $userInfo = $sessionManager->decodeTokenPayload($tokens['access_token']);

    $cookieValue = "{$cookieName}={$sessionId}; Path=/; HttpOnly; SameSite=Lax; Max-Age={$cookieTtl}";

    $response->getBody()->write(json_encode([
        'authenticated' => true,
        'user' => [
            'sub'   => $userInfo['sub']                   ?? null,
            'name'  => $userInfo['name']                  ?? null,
            'email' => $userInfo['email']                 ?? null,
            'roles' => $userInfo['realm_access']['roles'] ?? [],
        ],
    ]));

    return $response->withHeader('Content-Type', 'application/json');
});

// ─────────────────────────────────────────────────────────────────────────────
// GET /api/reports
//
// Защищённый прокси-эндпоинт: валидирует сессию, при необходимости
// обновляет токен, выполняет ротацию и возвращает данные отчёта.
// ─────────────────────────────────────────────────────────────────────────────
$app->get('/api/reports', function (Request $request, Response $response) use (
    $sessionManager, $keycloak, $cookieName, $cookieTtl
): Response {
    [$sessionId, $tokens, $errorResponse] = resolveSession(
        $request, $response, $sessionManager, $keycloak, $cookieName
    );

    if ($errorResponse !== null) {
        return $errorResponse;
    }

    // Ротация сессии при каждом запросе к защищённому ресурсу
    $newSessionId = $sessionManager->rotateSession(
        $sessionId,
        $tokens['access_token'],
        $tokens['refresh_token']
    );

    // Здесь был бы проксированный запрос к реальному API с Bearer-токеном.
    // Пока возвращаем заглушку.
    $userInfo = $sessionManager->decodeTokenPayload($tokens['access_token']);
    $cookieValue = "{$cookieName}={$newSessionId}; Path=/; HttpOnly; SameSite=Lax; Max-Age={$cookieTtl}";

    $response->getBody()->write(json_encode([
        'message'    => 'Reports data',
        'session_id' => $newSessionId, // для отладки ротации
        'user'       => $userInfo['preferred_username'] ?? 'unknown',
    ]));

    return $response
        ->withHeader('Content-Type', 'application/json')
        ->withHeader('Set-Cookie', $cookieValue);
});

// ─────────────────────────────────────────────────────────────────────────────
// DELETE /auth/session
//
// Logout: удаляет сессию из Redis и сбрасывает cookie.
// ─────────────────────────────────────────────────────────────────────────────
$app->delete('/auth/session', function (Request $request, Response $response) use (
    $sessionManager, $keycloak, $cookieName
): Response {
    $cookies   = $request->getCookieParams();
    $sessionId = $cookies[$cookieName] ?? null;

    if ($sessionId !== null) {
        $tokens = $sessionManager->getSession($sessionId);
        if ($tokens !== null) {
            $keycloak->logout($tokens['refresh_token']);
        }
        $sessionManager->destroySession($sessionId);
    }

    // Сбрасываем cookie: Max-Age=0 и просроченная дата
    $cookieValue = "{$cookieName}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0; Expires=Thu, 01 Jan 1970 00:00:00 GMT";

    return $response
        ->withStatus(200)
        ->withHeader('Content-Type', 'application/json')
        ->withHeader('Set-Cookie', $cookieValue)
        ->withBody((function () {
            $stream = \Slim\Psr7\Factory\StreamFactory::create();
            $body = $stream->createStream(json_encode(['ok' => true]));
            return $body;
        })());
});

// ─────────────────────────────────────────────────────────────────────────────
// Вспомогательная функция: resolveSession
//
// Читает session_id из cookie, загружает токены из Redis.
// Если access_token истёк — обновляет через refresh_token.
// Возвращает [sessionId, tokens, errorResponse].
// ─────────────────────────────────────────────────────────────────────────────
function resolveSession(
    Request $request,
    Response $response,
    SessionManager $sessionManager,
    KeycloakClient $keycloak,
    string $cookieName
): array {
    $cookies   = $request->getCookieParams();
    $sessionId = $cookies[$cookieName] ?? null;

    if ($sessionId === null) {
        $response->getBody()->write(json_encode(['error' => 'No session cookie']));
        return [null, null, $response->withStatus(401)->withHeader('Content-Type', 'application/json')];
    }

    $tokens = $sessionManager->getSession($sessionId);
    if ($tokens === null) {
        $response->getBody()->write(json_encode(['error' => 'Session not found or expired']));
        return [null, null, $response->withStatus(401)->withHeader('Content-Type', 'application/json')];
    }

    // Если access_token истёк — прозрачно обновляем через refresh_token
    if ($sessionManager->isAccessTokenExpired($tokens['access_token'])) {
        try {
            $newTokens = $keycloak->refreshToken($tokens['refresh_token']);
            $tokens['access_token']  = $newTokens['access_token'];
            $tokens['refresh_token'] = $newTokens['refresh_token'];
        } catch (\RuntimeException $e) {
            // refresh_token тоже истёк — требуется повторная авторизация
            $sessionManager->destroySession($sessionId);
            $response->getBody()->write(json_encode(['error' => 'Session expired, please login again']));
            return [null, null, $response->withStatus(401)->withHeader('Content-Type', 'application/json')];
        }
    }

    return [$sessionId, $tokens, null];
}

$app->run();
