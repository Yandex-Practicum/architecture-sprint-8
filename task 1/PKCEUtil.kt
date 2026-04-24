import java.security.MessageDigest
import java.util.Base64

object PKCEUtil {
    fun generateCodeVerifier(): String {
        val byteArray = ByteArray(64)
        SecureRandom().nextBytes(byteArray)
        return Base64.getUrlEncoder().withoutPadding().encodeToString(byteArray)
    }

    fun generateCodeChallenge(codeVerifier: String): String {
        val bytes = codeVerifier.toByteArray(Charsets.US_ASCII)
        val digest = MessageDigest.getInstance("SHA-256").digest(bytes)
        return Base64.getUrlEncoder().withoutPadding().encodeToString(digest)
    }
}

// AuthRepository.kt (часть, отвечающая за PKCE)
class AuthRepository(private val httpClient: HttpClient) {
    suspend fun loginWithPKCE(username: String, password: String) {
        val codeVerifier = PKCEUtil.generateCodeVerifier()
        val codeChallenge = PKCEUtil.generateCodeChallenge(codeVerifier)

        // Сохраняем codeVerifier в защищённом хранилище (EncryptedSharedPreferences)
        saveCodeVerifier(codeVerifier)

        // 1. Запрос кода авторизации (через WebView или Custom Tabs)
        val authUrl = "${KEYCLOAK_URL}/protocol/openid-connect/auth".toHttpUrl().newBuilder()
            .addQueryParameter("response_type", "code")
            .addQueryParameter("client_id", "bionic-mobile")
            .addQueryParameter("redirect_uri", "bionic://callback")
            .addQueryParameter("code_challenge", codeChallenge)
            .addQueryParameter("code_challenge_method", "S256")
            .addQueryParameter("scope", "openid profile email")
            .build()

        // Открываем WebView для входа пользователя, перехватываем redirect_uri с кодом
        val authCode = captureAuthorizationCode(authUrl) // предполагаемая функция

        // 2. Обмен кода на токены
        val tokenResponse = httpClient.post("${KEYCLOAK_URL}/protocol/openid-connect/token") {
            setBody(
                FormDataContent(
                    listOf(
                        "grant_type" to "authorization_code",
                        "code" to authCode,
                        "client_id" to "bionic-mobile",
                        "redirect_uri" to "bionic://callback",
                        "code_verifier" to codeVerifier
                    )
                )
            )
        }
        // Обработка ответа: сохраняем access_token, refresh_token
    }
}