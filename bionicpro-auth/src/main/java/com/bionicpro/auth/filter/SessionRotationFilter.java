package com.bionicpro.auth.filter;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpSession;
import org.springframework.security.authentication.AnonymousAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

@Component
public class SessionRotationFilter extends OncePerRequestFilter {

    private static final String SESSION_ID_HEADER = "X-Session-Id";

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {

        if (isAuthenticatedRequest(request)) {
            HttpSession session = request.getSession(false);
            if (session != null) {
                String newSessionId = request.changeSessionId();
                response.setHeader(SESSION_ID_HEADER, newSessionId);
            }
        }

        filterChain.doFilter(request, response);
    }

    private boolean isAuthenticatedRequest(HttpServletRequest request) {
        String path = request.getRequestURI();
        if (path.startsWith("/oauth2/") || path.startsWith("/login/") || path.equals("/auth/logout")
                || path.startsWith("/internal/")) {
            return false;
        }
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        return authentication != null
                && authentication.isAuthenticated()
                && !(authentication instanceof AnonymousAuthenticationToken);
    }
}
