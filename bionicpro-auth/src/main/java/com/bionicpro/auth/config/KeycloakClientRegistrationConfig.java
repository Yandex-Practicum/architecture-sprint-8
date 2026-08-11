package com.bionicpro.auth.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.oauth2.client.registration.ClientRegistration;
import org.springframework.security.oauth2.client.registration.ClientRegistrationRepository;
import org.springframework.security.oauth2.client.registration.InMemoryClientRegistrationRepository;
import org.springframework.security.oauth2.core.AuthorizationGrantType;
import org.springframework.security.oauth2.core.ClientAuthenticationMethod;
import org.springframework.security.oauth2.core.oidc.IdTokenClaimNames;

import java.util.Map;

@Configuration
public class KeycloakClientRegistrationConfig {

    @Bean
    public ClientRegistrationRepository clientRegistrationRepository(
            @Value("${keycloak.public-base-url}") String publicBaseUrl,
            @Value("${keycloak.internal-base-url}") String internalBaseUrl,
            @Value("${keycloak.realm}") String realm,
            @Value("${keycloak.client-id}") String clientId,
            @Value("${keycloak.redirect-uri}") String redirectUri) {

        String publicRealmUrl = publicBaseUrl + "/realms/" + realm;
        String internalRealmUrl = internalBaseUrl + "/realms/" + realm;

        ClientRegistration keycloak = ClientRegistration.withRegistrationId("keycloak")
                .clientId(clientId)
                .clientAuthenticationMethod(ClientAuthenticationMethod.NONE)
                .authorizationGrantType(AuthorizationGrantType.AUTHORIZATION_CODE)
                .redirectUri(redirectUri)
                .scope("openid", "profile", "email")
                .authorizationUri(publicRealmUrl + "/protocol/openid-connect/auth")
                .tokenUri(internalRealmUrl + "/protocol/openid-connect/token")
                .jwkSetUri(internalRealmUrl + "/protocol/openid-connect/certs")
                .userInfoUri(internalRealmUrl + "/protocol/openid-connect/userinfo")
                .userNameAttributeName(IdTokenClaimNames.SUB)
                .issuerUri(publicRealmUrl)
                .providerConfigurationMetadata(
                        Map.of("end_session_endpoint", publicRealmUrl + "/protocol/openid-connect/logout"))
                .clientName("Keycloak")
                .build();

        return new InMemoryClientRegistrationRepository(keycloak);
    }
}
