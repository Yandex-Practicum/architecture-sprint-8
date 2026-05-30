package ru.bionicpro.reports.controller;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpSession;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;
import ru.bionicpro.reports.service.SessionService;

import java.io.IOException;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.Base64;

@RestController
@RequestMapping("/auth")
@RequiredArgsConstructor
@Slf4j
public class AuthController {

    private final SessionService sessionService;

    @GetMapping("/token")
    public void getToken(HttpSession httpSession, HttpServletResponse response) throws IOException {
        log.info("Get token called, Session ID: {}", httpSession.getId());

        String accessToken = sessionService.getValidAccessToken(httpSession);

        response.setContentType("application/json");
        response.setHeader("Access-Control-Allow-Origin", "http://localhost:3000");
        response.setHeader("Access-Control-Allow-Credentials", "true");

        if (accessToken != null) {
            log.info("Access token retrieved successfully");
            response.getWriter().write(String.format(
                    "{\"accessToken\":\"%s\", \"tokenType\":\"Bearer\"}", accessToken
            ));
        } else {
            log.warn("No valid access token found");
            response.setStatus(401);
            response.getWriter().write("{\"error\":\"No valid access token\"}");
        }
    }

    @GetMapping("/login")
    public void login(HttpServletRequest request, HttpServletResponse response) throws IOException {
        String redirectUri = "http://localhost:8081/auth/callback";

        String codeVerifier = generateCodeVerifier();
        String codeChallenge = generateCodeChallenge(codeVerifier);

        // Сохраняем code_verifier в сессии для последующего использования
        request.getSession().setAttribute("code_verifier", codeVerifier);

        String keycloakLoginUrl = String.format(
                "http://localhost:8080/realms/reports-realm/protocol/openid-connect/auth" +
                        "?client_id=reports-frontend" +
                        "&response_type=code" +
                        "&redirect_uri=%s" +
                        "&scope=openid%%20profile%%20email" +
                        "&code_challenge=%s" +
                        "&code_challenge_method=S256",
                redirectUri, codeChallenge
        );

        log.info("=== LOGIN START ===");
        log.info("Redirecting to Keycloak: {}", keycloakLoginUrl);
        log.info("Code verifier stored: {}", codeVerifier);
        log.info("Code challenge: {}", codeChallenge);

        log.info("Redirecting to Keycloak with PKCE code_challenge: {}", codeChallenge);
        response.sendRedirect(keycloakLoginUrl);
    }

    @GetMapping("/callback")
    public void callback(
            @RequestParam String code,
            HttpServletRequest request,
            HttpServletResponse response,
            HttpSession httpSession) throws IOException {

        log.info("=== CALLBACK RECEIVED ===");
        log.info("Code: {}", code);

        try {
            String redirectUri = "http://localhost:8081/auth/callback";

            // Получаем сохраненный code_verifier из сессии
            String codeVerifier = (String) request.getSession().getAttribute("code_verifier");
            log.info("Code verifier from session: {}", codeVerifier);

            if (codeVerifier == null) {
                throw new RuntimeException("Code verifier not found in session");
            }

            // Передаем code_verifier в сервис для обмена токенов
            var session = sessionService.createSessionFromAuthCode(code, redirectUri, codeVerifier, httpSession);

            log.info("Authentication successful for user: {}", session.getUsername());

            // Явно добавляем заголовки CORS
            response.setHeader("Access-Control-Allow-Origin", "http://localhost:3000");
            response.setHeader("Access-Control-Allow-Credentials", "true");
            response.setHeader("Access-Control-Expose-Headers", "Set-Cookie, X-Session-Rotated");

            // Перенаправляем на фронтенд с параметром успеха
            response.sendRedirect("http://localhost:3000?auth=success");

        } catch (Exception e) {
            log.error("Authentication failed", e);
            response.sendRedirect("http://localhost:3000?auth=failed&error=" + e.getMessage());
        }
    }

    @PostMapping("/logout")
    public void logout(HttpSession httpSession, HttpServletResponse response) throws IOException {
        sessionService.invalidateSession(httpSession);
        response.sendRedirect("http://localhost:3000");
    }

    @GetMapping("/me")
    public void getCurrentUser(HttpSession httpSession, HttpServletResponse response) throws IOException {
        var session = sessionService.getCurrentSession(httpSession);
        if (session == null) {
            response.setStatus(401);
            response.getWriter().write("{\"error\":\"No active session\"}");
        } else {
            response.setContentType("application/json");
            response.getWriter().write(String.format(
                    "{\"username\":\"%s\",\"userId\":\"%s\",\"email\":\"%s\",\"roles\":%s,\"authenticated\":true}",
                    session.getUsername(), session.getUserId(), session.getEmail(),
                    new com.fasterxml.jackson.databind.ObjectMapper().writeValueAsString(session.getRealmRoles())
            ));
        }
    }

    @GetMapping("/check")
    public void checkAuth(HttpSession httpSession, HttpServletResponse response) throws IOException {

        log.info("Check auth called, Session ID: {}", httpSession.getId());

        String accessToken = sessionService.getValidAccessToken(httpSession);

        response.setContentType("application/json");
        response.setHeader("Access-Control-Allow-Origin", "http://localhost:3000");
        response.setHeader("Access-Control-Allow-Credentials", "true");

        if (accessToken != null) {
            log.info("Access token valid");
            response.getWriter().write("{\"authenticated\":true}");
        } else {
            log.warn("No valid access token");
            response.setStatus(401);
            response.getWriter().write("{\"authenticated\":false}");
        }
    }

    // Генерация code_verifier (43-128 символов)
    private String generateCodeVerifier() {
        byte[] codeVerifier = new byte[32];
        new SecureRandom().nextBytes(codeVerifier);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(codeVerifier);
    }

    // Генерация code_challenge методом S256
    private String generateCodeChallenge(String codeVerifier) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] digest = md.digest(codeVerifier.getBytes("US-ASCII"));
            return Base64.getUrlEncoder().withoutPadding().encodeToString(digest);
        } catch (Exception e) {
            throw new RuntimeException("Failed to generate code challenge", e);
        }
    }
}