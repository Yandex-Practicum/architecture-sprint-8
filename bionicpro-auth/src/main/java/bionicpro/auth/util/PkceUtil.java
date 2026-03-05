package bionicpro.auth.util;

import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.util.Base64;

/**
 * PKCE (RFC 7636) — генерация code_verifier и code_challenge.
 *
 * code_verifier: 32 случайных байта → Base64URL (43 символа)
 * code_challenge: BASE64URL(SHA-256(code_verifier))
 */
public final class PkceUtil {

    private static final SecureRandom SECURE_RANDOM = new SecureRandom();

    private PkceUtil() {}

    public static String generateCodeVerifier() {
        var bytes = new byte[32];
        SECURE_RANDOM.nextBytes(bytes);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }

    public static String generateCodeChallenge(String codeVerifier) {
        try {
            var digest = MessageDigest.getInstance("SHA-256");
            var hash = digest.digest(codeVerifier.getBytes(java.nio.charset.StandardCharsets.US_ASCII));
            return Base64.getUrlEncoder().withoutPadding().encodeToString(hash);
        } catch (NoSuchAlgorithmException e) {
            // SHA-256 гарантированно есть в любой JVM
            throw new RuntimeException("SHA-256 not available", e);
        }
    }

    /** Генерация криптографически стойкого ID (для session_id, state). */
    public static String generateSecureId() {
        var bytes = new byte[32];
        SECURE_RANDOM.nextBytes(bytes);
        return java.util.HexFormat.of().formatHex(bytes);
    }
}
