package com.bionicpro.auth.api;

import com.bionicpro.auth.config.AppProperties;
import com.bionicpro.auth.web.SessionAuthenticationFilter;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestAttribute;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.HttpServerErrorException;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;

@RestController
@RequestMapping("/api")
public class ReportsController {

    private final RestTemplate reportsRestTemplate;
    private final AppProperties appProperties;

    public ReportsController(RestTemplate reportsRestTemplate, AppProperties appProperties) {
        this.reportsRestTemplate = reportsRestTemplate;
        this.appProperties = appProperties;
    }

    /**
     * Прокси к сервису отчётов: access token передаётся как Bearer; пользователь определяется только по sub в JWT на стороне сервиса отчётов.
     */
    @GetMapping(value = "/reports", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<String> reports(
            @RequestAttribute(SessionAuthenticationFilter.ATTR_ACCESS_TOKEN) String accessToken) {
        String base = appProperties.getReportsServiceBaseUrl().replaceAll("/$", "");
        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(accessToken);
        HttpEntity<Void> entity = new HttpEntity<>(headers);
        try {
            return reportsRestTemplate.exchange(
                    base + "/reports",
                    HttpMethod.GET,
                    entity,
                    String.class);
        } catch (HttpClientErrorException | HttpServerErrorException e) {
            return ResponseEntity.status(e.getStatusCode()).contentType(MediaType.APPLICATION_JSON).body(e.getResponseBodyAsString());
        } catch (RestClientException e) {
            return ResponseEntity.status(HttpStatus.BAD_GATEWAY)
                    .contentType(MediaType.APPLICATION_JSON)
                    .body("{\"error\":\"reports_service_unavailable\"}");
        }
    }
}
