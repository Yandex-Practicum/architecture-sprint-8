<?php

declare(strict_types=1);

namespace App;

/**
 * Шифрует и дешифрует refresh_token с помощью AES-256-GCM.
 * Ключ берётся из переменной окружения SESSION_SECRET (32-байтный hex).
 * Метод GCM обеспечивает как конфиденциальность, так и аутентичность (AEAD).
 */
class TokenEncryptor
{
    private const CIPHER = 'aes-256-gcm';
    private const TAG_LENGTH = 16;

    private string $key;

    public function __construct()
    {
        $hex = $_ENV['SESSION_SECRET'] ?? '';
        if (strlen($hex) !== 64) {
            throw new \RuntimeException('SESSION_SECRET must be a 64-char hex string (32 bytes)');
        }
        $this->key = hex2bin($hex);
    }

    /**
     * Шифрует plaintext и возвращает base64url-encoded строку:
     * IV (12 bytes) + TAG (16 bytes) + ciphertext
     */
    public function encrypt(string $plaintext): string
    {
        $iv  = random_bytes(12);
        $tag = '';

        $ciphertext = openssl_encrypt(
            $plaintext,
            self::CIPHER,
            $this->key,
            OPENSSL_RAW_DATA,
            $iv,
            $tag,
            '',
            self::TAG_LENGTH
        );

        if ($ciphertext === false) {
            throw new \RuntimeException('Encryption failed');
        }

        return base64_encode($iv . $tag . $ciphertext);
    }

    /**
     * Дешифрует base64url-encoded строку, возвращённую методом encrypt().
     */
    public function decrypt(string $encoded): string
    {
        $raw = base64_decode($encoded, true);
        if ($raw === false) {
            throw new \RuntimeException('Invalid base64 payload');
        }

        $iv         = substr($raw, 0, 12);
        $tag        = substr($raw, 12, self::TAG_LENGTH);
        $ciphertext = substr($raw, 12 + self::TAG_LENGTH);

        $plaintext = openssl_decrypt(
            $ciphertext,
            self::CIPHER,
            $this->key,
            OPENSSL_RAW_DATA,
            $iv,
            $tag
        );

        if ($plaintext === false) {
            throw new \RuntimeException('Decryption failed: invalid tag or corrupted data');
        }

        return $plaintext;
    }
}
