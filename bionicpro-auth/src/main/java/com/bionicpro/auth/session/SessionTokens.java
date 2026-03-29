package com.bionicpro.auth.session;

import java.time.Instant;

/**
 * access_token в открытом виде в памяти; refresh_token хранится зашифрованным ({@link com.bionicpro.auth.crypto.TokenEncryption}).
 */
public record SessionTokens(
        String accessToken,
        String encryptedRefreshToken,
        Instant accessTokenExpiresAt,
        String subject
) {
}
