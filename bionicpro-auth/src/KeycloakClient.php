<?php

declare(strict_types=1);

namespace App;

use GuzzleHttp\Client;
use GuzzleHttp\Exception\GuzzleException;

/**
 * HTTP-клиент для взаимодействия с Keycloak token endpoint.
 * Выполняет обмен authorization code на токены и обновление access_token.
 */
class KeycloakClient
{
    private Client $http;
    private string $tokenUrl;
    private string $clientId;
    private string $redirectUri;

    public function __construct()
    {
        $this->http = new Client(['timeout' => 10]);
        $baseUrl    = rtrim($_ENV['KEYCLOAK_URL'], '/');
        $realm      = $_ENV['KEYCLOAK_REALM'];
        $this->tokenUrl    = "{$baseUrl}/realms/{$realm}/protocol/openid-connect/token";
        $this->clientId    = $_ENV['KEYCLOAK_CLIENT_ID'];
        $this->redirectUri = $_ENV['REDIRECT_URI'];
    }

    /**
     * Строит URL авторизации Keycloak с PKCE-параметрами.
     * Параметры code_verifier и code_challenge генерируются на бэкенде.
     */
    public function buildAuthorizationUrl(string $codeChallenge, string $state): string
    {
        $baseUrl = rtrim($_ENV['KEYCLOAK_URL'], '/');
        $realm   = $_ENV['KEYCLOAK_REALM'];
        $authUrl = "{$baseUrl}/realms/{$realm}/protocol/openid-connect/auth";

        return $authUrl . '?' . http_build_query([
            'response_type'         => 'code',
            'client_id'             => $this->clientId,
            'redirect_uri'          => $this->redirectUri,
            'scope'                 => 'openid profile email',
            'state'                 => $state,
            'code_challenge'        => $codeChallenge,
            'code_challenge_method' => 'S256',
        ]);
    }

    /**
     * Обменивает authorization code на access_token и refresh_token.
     * Отправляет code_verifier, который был сгенерирован на бэкенде.
     *
     * @return array{access_token: string, refresh_token: string, expires_in: int}
     * @throws \RuntimeException
     */
    public function exchangeCode(string $code, string $codeVerifier): array
    {
        try {
            $response = $this->http->post($this->tokenUrl, [
                'form_params' => [
                    'grant_type'    => 'authorization_code',
                    'client_id'     => $this->clientId,
                    'redirect_uri'  => $this->redirectUri,
                    'code'          => $code,
                    'code_verifier' => $codeVerifier,
                ],
            ]);

            return json_decode((string) $response->getBody(), true);
        } catch (GuzzleException $e) {
            throw new \RuntimeException('Failed to exchange code: ' . $e->getMessage(), 0, $e);
        }
    }

    /**
     * Обновляет access_token с помощью refresh_token.
     *
     * @return array{access_token: string, refresh_token: string, expires_in: int}
     * @throws \RuntimeException
     */
    public function refreshToken(string $refreshToken): array
    {
        try {
            $response = $this->http->post($this->tokenUrl, [
                'form_params' => [
                    'grant_type'    => 'refresh_token',
                    'client_id'     => $this->clientId,
                    'refresh_token' => $refreshToken,
                ],
            ]);

            return json_decode((string) $response->getBody(), true);
        } catch (GuzzleException $e) {
            throw new \RuntimeException('Failed to refresh token: ' . $e->getMessage(), 0, $e);
        }
    }
}
