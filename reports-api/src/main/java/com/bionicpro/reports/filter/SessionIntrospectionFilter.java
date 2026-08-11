package com.bionicpro.reports.filter;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpHeaders;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

@Component
public class SessionIntrospectionFilter extends OncePerRequestFilter {

    private static final Logger log = LoggerFactory.getLogger(SessionIntrospectionFilter.class);

    private final RestClient restClient;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public SessionIntrospectionFilter(@Value("${bionicpro.auth-internal-url}") String authInternalUrl) {
        this.restClient = RestClient.builder().baseUrl(authInternalUrl).build();
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                     FilterChain filterChain) throws ServletException, IOException {
        String cookieHeader = request.getHeader(HttpHeaders.COOKIE);
        if (cookieHeader != null && !cookieHeader.isBlank()) {
            introspect(cookieHeader).ifPresent(this::authenticate);
        }
        filterChain.doFilter(request, response);
    }

    private Optional<JsonNode> introspect(String cookieHeader) {
        try {
            String body = restClient.get()
                    .uri("/internal/session")
                    .header(HttpHeaders.COOKIE, cookieHeader)
                    .exchange((req, res) -> {
                        if (!res.getStatusCode().is2xxSuccessful()) {
                            return null;
                        }
                        return new String(res.getBody().readAllBytes());
                    });
            return body == null ? Optional.empty() : Optional.of(objectMapper.readTree(body));
        } catch (Exception e) {
            log.warn("Session introspection failed: {}", e.getMessage());
            return Optional.empty();
        }
    }

    private void authenticate(JsonNode session) {
        String username = session.path("username").asText(null);
        if (username == null) {
            return;
        }
        List<GrantedAuthority> authorities = new ArrayList<>();
        session.path("roles").forEach(role -> authorities.add(new SimpleGrantedAuthority("ROLE_" + role.asText())));

        var auth = new UsernamePasswordAuthenticationToken(username, null, authorities);
        SecurityContextHolder.getContext().setAuthentication(auth);
    }
}
