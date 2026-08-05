package com.bionicpro.auth.web;

import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.client.OAuth2AuthorizedClient;
import org.springframework.security.oauth2.client.annotation.RegisteredOAuth2AuthorizedClient;
import org.springframework.security.oauth2.core.oidc.user.OidcUser;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class SessionController {

    @GetMapping("/api/session")
    public SessionInfo session(@AuthenticationPrincipal OidcUser user,
                                @RegisteredOAuth2AuthorizedClient("keycloak") OAuth2AuthorizedClient authorizedClient) {
        return sessionInfo(user, authorizedClient);
    }

    @GetMapping("/internal/session")
    public SessionInfo internalSession(@AuthenticationPrincipal OidcUser user,
                                        @RegisteredOAuth2AuthorizedClient("keycloak") OAuth2AuthorizedClient authorizedClient) {
        return sessionInfo(user, authorizedClient);
    }

    private SessionInfo sessionInfo(OidcUser user, OAuth2AuthorizedClient authorizedClient) {
        var accessToken = authorizedClient.getAccessToken();
        return new SessionInfo(
                user.getPreferredUsername(),
                JwtRoles.fromAccessToken(accessToken.getTokenValue()),
                accessToken.getExpiresAt());
    }
}
