package ru.bionicpro.reports.controller;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpSession;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestMethod;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.reactive.function.client.WebClient;
import ru.bionicpro.reports.service.SessionService;

import java.util.Enumeration;
import java.util.Map;

@RestController
@RequiredArgsConstructor
@Slf4j
public class ProxyController {

    private final SessionService sessionService;
    private final WebClient webClient;

    @RequestMapping(value = "/api/**", method = {RequestMethod.GET, RequestMethod.POST, RequestMethod.PUT, RequestMethod.DELETE})
    public ResponseEntity<?> proxyRequest(
            HttpServletRequest request,
            HttpSession httpSession,
            @RequestBody(required = false) byte[] body) {

        // Get valid access token
        String accessToken = sessionService.getValidAccessToken(httpSession);
        if (accessToken == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                    .body(Map.of("error", "No valid session"));
        }

        // Build target URL
        String targetUrl = "http://localhost:8000" + request.getRequestURI().replace("/api", "");

        // Build request
        WebClient.RequestHeadersSpec<?> requestSpec;

        if (body != null && body.length > 0) {
            requestSpec = webClient.method(HttpMethod.valueOf(request.getMethod()))
                    .uri(targetUrl)
                    .header("Authorization", "Bearer " + accessToken)
                    .contentType(MediaType.APPLICATION_JSON)
                    .bodyValue(body);
        } else {
            requestSpec = webClient.method(HttpMethod.valueOf(request.getMethod()))
                    .uri(targetUrl)
                    .header("Authorization", "Bearer " + accessToken);
        }

        // Copy headers (except auth and cookie)
        Enumeration<String> headerNames = request.getHeaderNames();
        while (headerNames.hasMoreElements()) {
            String headerName = headerNames.nextElement();
            if (!"Authorization".equalsIgnoreCase(headerName) && !"Cookie".equalsIgnoreCase(headerName)) {
                String headerValue = request.getHeader(headerName);
                requestSpec.header(headerName, headerValue);
            }
        }

        try {
            ResponseEntity<byte[]> response = requestSpec
                    .retrieve()
                    .toEntity(byte[].class)
                    .block();

            if (response != null) {
                return ResponseEntity.status(response.getStatusCode())
                        .headers(response.getHeaders())
                        .body(response.getBody());
            } else {
                return ResponseEntity.status(HttpStatus.BAD_GATEWAY).build();
            }
        } catch (Exception e) {
            log.error("Proxy request failed", e);
            return ResponseEntity.status(HttpStatus.BAD_GATEWAY)
                    .body(Map.of("error", "Upstream service error"));
        }
    }
}