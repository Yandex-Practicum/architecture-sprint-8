package ru.bionicpro.api;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import software.amazon.awssdk.auth.credentials.AwsBasicCredentials;
import software.amazon.awssdk.auth.credentials.StaticCredentialsProvider;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.s3.S3Client;

import java.net.URI;

@Configuration(proxyBeanMethods = false)
public final class S3Configuration {

    @Bean
    public S3Client s3Client(
            @Value("${app.s3.endpoint}") String s3Endpoint,
            @Value("${app.s3.region}") String s3Region,
            @Value("${app.s3.access-key}") String s3AccessKey,
            @Value("${app.s3.secret-key}") String s3SecretKey
    ) {
        return S3Client.builder()
                .endpointOverride(URI.create(s3Endpoint))
                .region(Region.of(s3Region))
                .credentialsProvider(StaticCredentialsProvider.create(AwsBasicCredentials.create(
                        s3AccessKey,
                        s3SecretKey
                )))
                .forcePathStyle(true)
                .build();
    }

}
