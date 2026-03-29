package com.bionicpro.auth.oauth;

import com.bionicpro.auth.config.AppProperties;
import com.bionicpro.auth.crypto.TokenEncryption;
import com.bionicpro.auth.session.SessionTokenStore;
import com.bionicpro.auth.session.SessionTokens;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpSession;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseCookie;
import org.springframework.security.core.Authentication;
import org.springframework.security.oauth2.client.OAuth2AuthorizedClient;
import org.springframework.security.oauth2.client.OAuth2AuthorizedClientService;
import org.springframework.security.oauth2.client.authentication.OAuth2AuthenticationToken;
import org.springframework.security.oauth2.core.OAuth2AccessToken;
import org.springframework.security.oauth2.core.OAuth2RefreshToken;
import org.springframework.security.web.authentication.SimpleUrlAuthenticationSuccessHandler;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

import java.io.IOException;
import java.time.Duration;
import java.time.Instant;
import java.util.UUID;

@Component
public class OAuth2LoginSuccessHandler extends SimpleUrlAuthenticationSuccessHandler {

    private final OAuth2AuthorizedClientService authorizedClientService;
    private final SessionTokenStore sessionTokenStore;
    private final TokenEncryption tokenEncryption;
    private final AppProperties appProperties;

    public OAuth2LoginSuccessHandler(
            OAuth2AuthorizedClientService authorizedClientService,
            SessionTokenStore sessionTokenStore,
            TokenEncryption tokenEncryption,
            AppProperties appProperties) {
        this.authorizedClientService = authorizedClientService;
        this.sessionTokenStore = sessionTokenStore;
        this.tokenEncryption = tokenEncryption;
        this.appProperties = appProperties;
    }

    @Override
    public void onAuthenticationSuccess(HttpServletRequest request, HttpServletResponse response,
                                        Authentication authentication) throws IOException, ServletException {
        if (!(authentication instanceof OAuth2AuthenticationToken oauthToken)) {
            super.onAuthenticationSuccess(request, response, authentication);
            return;
        }

        String registrationId = oauthToken.getAuthorizedClientRegistrationId();
        OAuth2AuthorizedClient client = authorizedClientService.loadAuthorizedClient(
                registrationId, oauthToken.getName());
        if (client == null) {
            response.sendError(HttpServletResponse.SC_INTERNAL_SERVER_ERROR, "No OAuth2 client");
            return;
        }

        OAuth2AccessToken accessToken = client.getAccessToken();
        String access = accessToken.getTokenValue();
        Instant exp = accessToken.getExpiresAt() != null
                ? accessToken.getExpiresAt()
                : Instant.now().plusSeconds(120);

        OAuth2RefreshToken refresh = client.getRefreshToken();
        String refreshPlain = refresh != null ? refresh.getTokenValue() : null;
        String encryptedRefresh = StringUtils.hasText(refreshPlain) ? tokenEncryption.encrypt(refreshPlain) : "";

        HttpSession httpSession = request.getSession(false);
        if (httpSession != null) {
            httpSession.invalidate();
        }

        String sessionId = UUID.randomUUID().toString();
        String subject = oauthToken.getPrincipal().getName();
        sessionTokenStore.save(sessionId, new SessionTokens(access, encryptedRefresh, exp, subject));

        authorizedClientService.removeAuthorizedClient(registrationId, oauthToken.getName());

        appendSessionCookie(response, sessionId);
        getRedirectStrategy().sendRedirect(request, response, appProperties.getFrontendUrl());
    }

    private void appendSessionCookie(HttpServletResponse response, String sessionId) {
        ResponseCookie cookie = ResponseCookie.from(appProperties.getSessionCookieName(), sessionId)
                .httpOnly(true)
                .secure(appProperties.isCookieSecure())
                .path("/")
                .maxAge(Duration.ofSeconds(appProperties.getSessionMaxAgeSeconds()))
                .sameSite("Lax")
                .build();
        response.addHeader(HttpHeaders.SET_COOKIE, cookie.toString());
    }
}
