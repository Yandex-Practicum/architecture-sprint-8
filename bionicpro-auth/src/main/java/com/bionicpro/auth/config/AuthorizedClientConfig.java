package com.bionicpro.auth.config;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.convert.converter.Converter;
import org.springframework.http.RequestEntity;
import org.springframework.security.oauth2.client.OAuth2AuthorizedClientManager;
import org.springframework.security.oauth2.client.OAuth2AuthorizedClientProvider;
import org.springframework.security.oauth2.client.OAuth2AuthorizedClientProviderBuilder;
import org.springframework.security.oauth2.client.RefreshTokenOAuth2AuthorizedClientProvider;
import org.springframework.security.oauth2.client.endpoint.DefaultRefreshTokenTokenResponseClient;
import org.springframework.security.oauth2.client.endpoint.OAuth2RefreshTokenGrantRequest;
import org.springframework.security.oauth2.client.endpoint.OAuth2RefreshTokenGrantRequestEntityConverter;
import org.springframework.security.oauth2.client.registration.ClientRegistrationRepository;
import org.springframework.security.oauth2.client.web.DefaultOAuth2AuthorizedClientManager;
import org.springframework.security.oauth2.client.web.OAuth2AuthorizedClientRepository;
import org.springframework.security.oauth2.core.ClientAuthenticationMethod;
import org.springframework.security.oauth2.core.endpoint.OAuth2ParameterNames;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;

import java.time.Duration;
import java.util.HashMap;
import java.util.Map;

@Configuration
public class AuthorizedClientConfig {

    @Bean
    public OAuth2AuthorizedClientManager authorizedClientManager(
            ClientRegistrationRepository clientRegistrationRepository,
            OAuth2AuthorizedClientRepository authorizedClientRepository) {

        OAuth2AuthorizedClientProvider authorizedClientProvider = OAuth2AuthorizedClientProviderBuilder.builder()
                .authorizationCode()
                .provider(refreshTokenProvider())
                .build();

        DefaultOAuth2AuthorizedClientManager manager =
                new DefaultOAuth2AuthorizedClientManager(clientRegistrationRepository, authorizedClientRepository);
        manager.setAuthorizedClientProvider(authorizedClientProvider);
        manager.setContextAttributesMapper(request -> {
            Map<String, Object> attributes = new HashMap<>();
            ServletRequestAttributes servletRequestAttributes =
                    (ServletRequestAttributes) RequestContextHolder.getRequestAttributes();
            if (servletRequestAttributes != null) {
                HttpServletRequest httpRequest = servletRequestAttributes.getRequest();
                HttpServletResponse httpResponse = servletRequestAttributes.getResponse();
                attributes.put(HttpServletRequest.class.getName(), httpRequest);
                attributes.put(HttpServletResponse.class.getName(), httpResponse);
            }
            return attributes;
        });
        return manager;
    }

    private RefreshTokenOAuth2AuthorizedClientProvider refreshTokenProvider() {
        OAuth2RefreshTokenGrantRequestEntityConverter defaultConverter =
                new OAuth2RefreshTokenGrantRequestEntityConverter();
        Converter<OAuth2RefreshTokenGrantRequest, RequestEntity<?>> converter = request -> {
            RequestEntity<?> entity = defaultConverter.convert(request);
            @SuppressWarnings("unchecked")
            MultiValueMap<String, String> body = (MultiValueMap<String, String>) entity.getBody();
            MultiValueMap<String, String> newBody = new LinkedMultiValueMap<>(body != null ? body : Map.of());
            if (request.getClientRegistration().getClientAuthenticationMethod().equals(ClientAuthenticationMethod.NONE)) {
                newBody.set(OAuth2ParameterNames.CLIENT_ID, request.getClientRegistration().getClientId());
            }
            return new RequestEntity<>(newBody, entity.getHeaders(), entity.getMethod(), entity.getUrl());
        };

        DefaultRefreshTokenTokenResponseClient responseClient = new DefaultRefreshTokenTokenResponseClient();
        responseClient.setRequestEntityConverter(converter);

        RefreshTokenOAuth2AuthorizedClientProvider provider = new RefreshTokenOAuth2AuthorizedClientProvider();
        provider.setAccessTokenResponseClient(responseClient);
        provider.setClockSkew(Duration.ofSeconds(20));
        return provider;
    }
}
