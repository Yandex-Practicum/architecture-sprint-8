package com.bionicpro.auth.api;

import com.bionicpro.auth.config.AppProperties;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.HttpServerErrorException;
import org.springframework.web.client.RestTemplate;

import jakarta.servlet.http.HttpServletRequest;
import java.net.URI;

/**
 * Прокси к Nginx+MinIO (эмуляция CDN): браузер запрашивает отчёт с того же хоста, что и /api,
 * без прямого обращения к localhost:8090 (CORS и недоступность порта из контейнера фронта).
 */
@RestController
public class CdnProxyController {

    private final RestTemplate restTemplate;
    private final AppProperties appProperties;

    public CdnProxyController(RestTemplate restTemplate, AppProperties appProperties) {
        this.restTemplate = restTemplate;
        this.appProperties = appProperties;
    }

    @GetMapping("/reports-cdn/**")
    public ResponseEntity<byte[]> proxy(HttpServletRequest request) {
        String uri = request.getRequestURI();
        String qs = request.getQueryString();
        String ctx = request.getContextPath() != null ? request.getContextPath() : "";
        String prefix = ctx + "/reports-cdn";
        if (!uri.startsWith(prefix)) {
            return ResponseEntity.notFound().build();
        }
        String suffix = uri.substring(prefix.length());
        if (suffix.isEmpty()) {
            suffix = "/";
        }
        if (suffix.contains("..")) {
            return ResponseEntity.badRequest().build();
        }
        String base = appProperties.getCdnProxyTargetUrl().replaceAll("/$", "");
        String target = base + suffix + (qs != null ? "?" + qs : "");

        try {
            ResponseEntity<byte[]> upstream = restTemplate.exchange(
                    URI.create(target),
                    HttpMethod.GET,
                    null,
                    byte[].class);
            return withForwardedHeaders(upstream);
        } catch (HttpClientErrorException | HttpServerErrorException e) {
            HttpStatusCode status = e.getStatusCode();
            byte[] body = e.getResponseBodyAsByteArray();
            HttpHeaders h = new HttpHeaders();
            if (e.getResponseHeaders() != null) {
                if (e.getResponseHeaders().getContentType() != null) {
                    h.setContentType(e.getResponseHeaders().getContentType());
                }
            }
            return new ResponseEntity<>(body, h, status);
        }
    }

    private static ResponseEntity<byte[]> withForwardedHeaders(ResponseEntity<byte[]> upstream) {
        HttpHeaders out = new HttpHeaders();
        HttpHeaders in = upstream.getHeaders();
        if (in.getContentType() != null) {
            out.setContentType(in.getContentType());
        }
        String cc = in.getFirst(HttpHeaders.CACHE_CONTROL);
        if (cc != null) {
            out.set(HttpHeaders.CACHE_CONTROL, cc);
        }
        String xs = in.getFirst("X-Cache-Status");
        if (xs != null) {
            out.set("X-Cache-Status", xs);
        }
        return new ResponseEntity<>(upstream.getBody(), out, upstream.getStatusCode());
    }
}
