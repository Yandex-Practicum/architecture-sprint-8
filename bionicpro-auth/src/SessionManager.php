<?php

declare(strict_types=1);

namespace App;

use Predis\Client as RedisClient;
use Ramsey\Uuid\Uuid;

/**
 * Управляет сессиями в Redis.
 *
 * Структура ключей:
 *   session:{id}:access_token    → JWT (plaintext)     TTL = SESSION_TTL
 *   session:{id}:refresh_token   → зашифрован AES-GCM  TTL = SESSION_TTL
 *   session:{id}:user_info       → JSON                TTL = SESSION_TTL
 *
 *   pkce:{state}:verifier        → code_verifier       TTL = 600s
 *
 * Ротация сессии при каждом запросе к защищённому ресурсу:
 * старый session_id удаляется, создаётся новый с теми же токенами.
 * Это предотвращает Session Fixation Attack.
 */
class SessionManager
{
    private RedisClient $redis;
    private TokenEncryptor $encryptor;
    private int $sessionTtl;

    public function __construct(RedisClient $redis, TokenEncryptor $encryptor)
    {
        $this->redis      = $redis;
        $this->encryptor  = $encryptor;
        $this->sessionTtl = (int) ($_ENV['SESSION_TTL'] ?? 1800);
    }

    // ─── PKCE helpers ────────────────────────────────────────────────────────

    /**
     * Генерирует PKCE code_verifier и code_challenge на стороне бэкенда.
     * code_verifier сохраняется в Redis по ключу pkce:{state}, TTL = 10 мин.
     *
     * @return array{state: string, code_challenge: string, authorization_url: string}
     */
    public function initiatePkceFlow(KeycloakClient $keycloak): array
    {
        $state        = Uuid::uuid4()->toString();
        $codeVerifier = $this->generateCodeVerifier();
        $codeChallenge = $this->computeCodeChallenge($codeVerifier);

        // Сохраняем verifier — бэкенд использует его при обмене кода
        $this->redis->setex("pkce:{$state}:verifier", 600, $codeVerifier);

        $authorizationUrl = $keycloak->buildAuthorizationUrl($codeChallenge, $state);

        return [
            'state'             => $state,
            'code_challenge'    => $codeChallenge,
            'authorization_url' => $authorizationUrl,
        ];
    }

    /**
     * Извлекает и удаляет code_verifier из Redis по state.
     */
    public function consumeCodeVerifier(string $state): ?string
    {
        $key      = "pkce:{$state}:verifier";
        $verifier = $this->redis->get($key);
        if ($verifier !== null) {
            $this->redis->del([$key]);
        }
        return $verifier;
    }

    // ─── Session lifecycle ────────────────────────────────────────────────────

    /**
     * Создаёт новую сессию: сохраняет access_token (plaintext) и
     * refresh_token (зашифрован AES-256-GCM) в Redis.
     */
    public function createSession(string $accessToken, string $refreshToken): string
    {
        $sessionId = Uuid::uuid4()->toString();
        $this->writeSession($sessionId, $accessToken, $refreshToken);
        return $sessionId;
    }

    /**
     * Читает сессию из Redis. Возвращает null если сессия не найдена.
     *
     * @return array{access_token: string, refresh_token: string}|null
     */
    public function getSession(string $sessionId): ?array
    {
        $at = $this->redis->get("session:{$sessionId}:access_token");
        $rt = $this->redis->get("session:{$sessionId}:refresh_token");

        if ($at === null || $rt === null) {
            return null;
        }

        return [
            'access_token'  => $at,
            'refresh_token' => $this->encryptor->decrypt($rt),
        ];
    }

    /**
     * Ротация сессии: удаляет старые ключи, создаёт новый session_id.
     * Вызывается при каждом успешном запросе к защищённому ресурсу.
     * Защищает от Session Fixation Attack.
     */
    public function rotateSession(string $oldSessionId, string $accessToken, string $refreshToken): string
    {
        $this->destroySession($oldSessionId);
        return $this->createSession($accessToken, $refreshToken);
    }

    /**
     * Уничтожает сессию — удаляет все ключи из Redis.
     */
    public function destroySession(string $sessionId): void
    {
        $this->redis->del([
            "session:{$sessionId}:access_token",
            "session:{$sessionId}:refresh_token",
        ]);
    }

    // ─── JWT helpers ─────────────────────────────────────────────────────────

    /**
     * Проверяет, истёк ли access_token (по полю exp в payload JWT).
     * Добавляет 10-секундный буфер для предотвращения граничных состояний.
     */
    public function isAccessTokenExpired(string $accessToken): bool
    {
        $parts = explode('.', $accessToken);
        if (count($parts) !== 3) {
            return true;
        }

        $payload = json_decode(base64_decode(strtr($parts[1], '-_', '+/')), true);
        if (!isset($payload['exp'])) {
            return true;
        }

        return (time() + 10) >= (int) $payload['exp'];
    }

    /**
     * Декодирует payload JWT без верификации подписи.
     * Подпись верифицирует Keycloak при вызове /userinfo или при resource-server.
     */
    public function decodeTokenPayload(string $accessToken): array
    {
        $parts = explode('.', $accessToken);
        if (count($parts) !== 3) {
            return [];
        }
        return json_decode(base64_decode(strtr($parts[1], '-_', '+/')), true) ?? [];
    }

    // ─── Private ─────────────────────────────────────────────────────────────

    private function writeSession(string $sessionId, string $accessToken, string $refreshToken): void
    {
        $encryptedRefresh = $this->encryptor->encrypt($refreshToken);

        $this->redis->setex("session:{$sessionId}:access_token",  $this->sessionTtl, $accessToken);
        $this->redis->setex("session:{$sessionId}:refresh_token", $this->sessionTtl, $encryptedRefresh);
    }

    /** Генерирует cryptographically-secure code_verifier (43–128 chars, Base64url). */
    private function generateCodeVerifier(): string
    {
        return rtrim(strtr(base64_encode(random_bytes(32)), '+/', '-_'), '=');
    }

    /** Вычисляет code_challenge = BASE64URL(SHA256(code_verifier)). */
    private function computeCodeChallenge(string $verifier): string
    {
        return rtrim(strtr(base64_encode(hash('sha256', $verifier, true)), '+/', '-_'), '=');
    }
}
