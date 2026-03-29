package com.bionicpro.auth.api;

import com.bionicpro.auth.config.AppProperties;
import com.bionicpro.auth.session.SessionTokenStore;
import jakarta.servlet.http.Cookie;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseCookie;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Arrays;
import java.util.Optional;

@RestController
@RequestMapping("/api")
public class LogoutController {

    private final SessionTokenStore sessionTokenStore;
    private final AppProperties appProperties;

    public LogoutController(SessionTokenStore sessionTokenStore, AppProperties appProperties) {
        this.sessionTokenStore = sessionTokenStore;
        this.appProperties = appProperties;
    }

    @PostMapping("/logout")
    public ResponseEntity<Void> logout(HttpServletRequest request, HttpServletResponse response) {
        Optional<String> cookieSessionId = readSessionCookie(request);
        cookieSessionId.ifPresent(sessionTokenStore::remove);

        ResponseCookie cleared = ResponseCookie.from(appProperties.getSessionCookieName(), "")
                .httpOnly(true)
                .secure(appProperties.isCookieSecure())
                .path("/")
                .maxAge(0)
                .sameSite("Lax")
                .build();
        response.addHeader(HttpHeaders.SET_COOKIE, cleared.toString());
        return ResponseEntity.noContent().build();
    }

    private Optional<String> readSessionCookie(HttpServletRequest request) {
        if (request.getCookies() == null) {
            return Optional.empty();
        }
        return Arrays.stream(request.getCookies())
                .filter(c -> appProperties.getSessionCookieName().equals(c.getName()))
                .map(Cookie::getValue)
                .findFirst();
    }
}
