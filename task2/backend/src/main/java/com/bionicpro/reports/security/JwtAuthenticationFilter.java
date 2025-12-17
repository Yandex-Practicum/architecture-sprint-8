package com.bionicpro.reports.security;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.Collections;
import java.util.List;

@Component
public class JwtAuthenticationFilter extends OncePerRequestFilter {

    @Override
    protected void doFilterInternal(HttpServletRequest request, 
                                   HttpServletResponse response, 
                                   FilterChain filterChain) 
            throws ServletException, IOException {
        
        String authHeader = request.getHeader("Authorization");
        
        if (authHeader != null && authHeader.startsWith("Bearer ")) {
            String token = authHeader.substring(7);
            
            try {
                // В реальной реализации здесь должна быть валидация JWT токена
                // и извлечение информации о пользователе из токена
                // Для примера используем упрощённую логику
                UserInfo userInfo = extractUserInfoFromToken(token);
                
                if (userInfo != null) {
                    List<SimpleGrantedAuthority> authorities = Collections.singletonList(
                        new SimpleGrantedAuthority("ROLE_USER")
                    );
                    
                    UsernamePasswordAuthenticationToken authentication = 
                        new UsernamePasswordAuthenticationToken(
                            userInfo, 
                            null, 
                            authorities
                        );
                    
                    SecurityContextHolder.getContext().setAuthentication(authentication);
                }
            } catch (Exception e) {
                logger.error("Ошибка при обработке JWT токена", e);
            }
        }
        
        filterChain.doFilter(request, response);
    }

    /**
     * Извлекает информацию о пользователе из JWT токена
     * В реальной реализации здесь должна быть полная валидация токена
     */
    private UserInfo extractUserInfoFromToken(String token) {
        try {
            // В реальной реализации здесь должна быть валидация JWT токена
            // через io.jsonwebtoken библиотеку:
            //
            // Jwts.parserBuilder()
            //     .setSigningKey(getSigningKey())
            //     .build()
            //     .parseClaimsJws(token)
            //     .getBody();
            //
            // Для примера используем упрощённую логику извлечения user_id из токена
            // В production нужно:
            // 1. Проверить подпись токена
            // 2. Проверить срок действия (expiration)
            // 3. Извлечь user_id и email из claims
            
            // Временная заглушка: извлекаем user_id из токена
            // В реальности это должно быть из claims токена после валидации
            // Для разработки можно использовать токен от Keycloak и извлекать данные из него
            
            // Пример для Keycloak токена (упрощённо):
            // Claims claims = Jwts.parserBuilder()
            //     .setSigningKey(keycloakPublicKey)
            //     .build()
            //     .parseClaimsJws(token)
            //     .getBody();
            // Long userId = Long.parseLong(claims.get("user_id").toString());
            // String email = claims.get("email").toString();
            
            // Заглушка для разработки - в production заменить на реальную валидацию
            // Можно использовать библиотеку для работы с Keycloak токенами
            return new UserInfo(1L, "user1@example.com");
        } catch (Exception e) {
            logger.error("Ошибка при извлечении информации из токена", e);
            return null;
        }
    }

    /**
     * Класс для хранения информации о пользователе
     */
    public static class UserInfo {
        private final Long userId;
        private final String email;

        public UserInfo(Long userId, String email) {
            this.userId = userId;
            this.email = email;
        }

        public Long getUserId() {
            return userId;
        }

        public String getEmail() {
            return email;
        }
    }
}

