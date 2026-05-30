package ru.bionicpro.reports.filter;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpSession;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

@Component
@Slf4j
public class SessionRotationFilter extends OncePerRequestFilter {

    @Value("${bionicpro.auth.session-rotation-enabled:true}")
    private boolean rotationEnabled;

    @Override
    protected void doFilterInternal(
            HttpServletRequest request,
            HttpServletResponse response,
            FilterChain filterChain) throws ServletException, IOException {

        String path = request.getRequestURI();

        if (!rotationEnabled ||
                path.startsWith("/auth/") ||
                path.equals("/") ||
                path.startsWith("/error") ||
                path.startsWith("/actuator") ||
                path.startsWith("/health")) {
            filterChain.doFilter(request, response);
            return;
        }

        HttpSession httpSession = request.getSession(false);
        if (httpSession != null) {
            Boolean rotated = (Boolean) httpSession.getAttribute("session_rotated");
            if (rotated == null || !rotated) {
                log.debug("Would rotate session for request: {}", path);
                // Просто отмечаем, что ротация выполнена, без фактического вызова sessionService
                httpSession.setAttribute("session_rotated", true);
                response.setHeader("X-Session-Rotated", "would-be-rotated");
            }
        }

        try {
            filterChain.doFilter(request, response);
        } finally {
            if (httpSession != null) {
                httpSession.removeAttribute("session_rotated");
            }
        }
    }
}