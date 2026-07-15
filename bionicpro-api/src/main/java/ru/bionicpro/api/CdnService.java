package ru.bionicpro.api;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.time.LocalDate;

@Component
public final class CdnService {

    private final String baseUrl;

    public CdnService(
            @Value("${app.cdn.base-url}") String baseUrl
    ) {
        this.baseUrl = baseUrl;
    }

    public String buildUrl(String userId, LocalDate reportDate) {
        return String.format("%s/%s/%s.json", baseUrl, userId, reportDate);
    }

}
