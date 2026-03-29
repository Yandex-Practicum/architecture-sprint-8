package com.bionicpro.auth.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.oauth2.client.oidc.userinfo.OidcUserService;

/**
 * Не дергаем Keycloak /userinfo: при разных URL (localhost vs keycloak в Docker) access token
 * иногда не проходит validate_access_token на userinfo, хотя код обмена и ID token валидны.
 * Для логина достаточно claims из ID token (openid + profile + email).
 */
@Configuration
public class OidcUserInfoDisabledConfig {

    @Bean
    OidcUserService oidcUserService() {
        OidcUserService delegate = new OidcUserService();
        delegate.setRetrieveUserInfo(userRequest -> false);
        return delegate;
    }
}
