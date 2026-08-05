package com.bionicpro.reports.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import software.amazon.awssdk.auth.credentials.AwsBasicCredentials;
import software.amazon.awssdk.auth.credentials.StaticCredentialsProvider;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.S3Configuration;

import java.net.URI;

@Configuration
public class S3Config {

    @Bean
    public S3Client s3Client(@Value("${bionicpro.s3-endpoint}") String endpoint,
                              @Value("${bionicpro.s3-access-key}") String accessKey,
                              @Value("${bionicpro.s3-secret-key}") String secretKey) {
        return S3Client.builder()
                .endpointOverride(URI.create(endpoint))
                .serviceConfiguration(S3Configuration.builder().pathStyleAccessEnabled(true).build())
                .region(Region.US_EAST_1)
                .credentialsProvider(StaticCredentialsProvider.create(AwsBasicCredentials.create(accessKey, secretKey)))
                .build();
    }
}
