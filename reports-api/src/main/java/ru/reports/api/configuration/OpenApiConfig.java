package ru.reports.api.configuration;

import io.swagger.v3.oas.models.Components;
import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.security.OAuthFlow;
import io.swagger.v3.oas.models.security.OAuthFlows;
import io.swagger.v3.oas.models.security.Scopes;
import io.swagger.v3.oas.models.security.SecurityScheme;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class OpenApiConfig {

    private static final String REALM_URL = "http://localhost:8080/realms/reports-realm";
    private static final String SECURITY_SCHEME_NAME = "keycloak-oauth2";

    @Bean
    public OpenAPI openAPI() {
        OAuthFlow authorizationCodeFlow = new OAuthFlow()
                .authorizationUrl(REALM_URL + "/protocol/openid-connect/auth")
                .tokenUrl(REALM_URL + "/protocol/openid-connect/token")
                .scopes(new Scopes()
                        .addString("openid", "OpenID Connect")
                        .addString("profile", "User profile")
                        .addString("email", "User email"));

        SecurityScheme securityScheme = new SecurityScheme()
                .type(SecurityScheme.Type.OAUTH2)
                .flows(new OAuthFlows().authorizationCode(authorizationCodeFlow));

        return new OpenAPI()
                .components(new Components()
                        .addSecuritySchemes(SECURITY_SCHEME_NAME, securityScheme));
    }
}