package ru.bionicpro.api;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import software.amazon.awssdk.core.sync.RequestBody;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.HeadObjectRequest;
import software.amazon.awssdk.services.s3.model.NoSuchKeyException;
import software.amazon.awssdk.services.s3.model.PutObjectRequest;

import java.time.Instant;
import java.time.LocalDate;
import java.time.temporal.ChronoUnit;

@Component
public final class S3Service {

    private final S3Client s3Client;

    private final String s3Bucket;

    public S3Service(
            S3Client s3Client,
            @Value("${app.s3.bucket}") String s3Bucket
    ) {
        this.s3Client = s3Client;
        this.s3Bucket = s3Bucket;
    }

    public String buildKey(String userId, LocalDate reportDate) {
        return String.format("%s/%s.json", userId, reportDate);
    }

    public boolean exists(String s3Key) {
        try {
            HeadObjectRequest headObjectResponse = HeadObjectRequest.builder()
                    .bucket(s3Bucket)
                    .key(s3Key)
                    .build();
            s3Client.headObject(headObjectResponse);

            return true;
        } catch (NoSuchKeyException e) {
            return false;
        }
    }

    public void upload(String s3Key, byte[] bytes) {
        PutObjectRequest putObjectRequest = PutObjectRequest.builder()
                .bucket(s3Bucket)
                .key(s3Key)
                .contentType("application/json")
                .expires(Instant.now().plus(1, ChronoUnit.DAYS))
                .build();
        s3Client.putObject(putObjectRequest, RequestBody.fromBytes(bytes));
    }

}
