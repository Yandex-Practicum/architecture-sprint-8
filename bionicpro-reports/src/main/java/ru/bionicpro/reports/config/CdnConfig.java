package ru.bionicpro.reports.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

@Data
@Configuration
@ConfigurationProperties(prefix = "cdn")
public class CdnConfig {
    private String baseUrl;
}
