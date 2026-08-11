package com.bionicpro.reports.service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import software.amazon.awssdk.core.sync.RequestBody;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.HeadObjectRequest;
import software.amazon.awssdk.services.s3.model.NoSuchKeyException;
import software.amazon.awssdk.services.s3.model.PutObjectRequest;
import software.amazon.awssdk.services.s3.model.S3Exception;

@Service
public class ReportStorageService {

    private final S3Client s3Client;
    private final String bucket;
    private final String cdnBaseUrl;

    public ReportStorageService(S3Client s3Client,
                                 @Value("${bionicpro.s3-bucket}") String bucket,
                                 @Value("${bionicpro.cdn-base-url}") String cdnBaseUrl) {
        this.s3Client = s3Client;
        this.bucket = bucket;
        this.cdnBaseUrl = cdnBaseUrl;
    }

    public boolean exists(String key) {
        try {
            s3Client.headObject(HeadObjectRequest.builder().bucket(bucket).key(key).build());
            return true;
        } catch (NoSuchKeyException e) {
            return false;
        } catch (S3Exception e) {
            if (e.statusCode() == 404) {
                return false;
            }
            throw e;
        }
    }

    public void put(String key, byte[] content) {
        s3Client.putObject(
                PutObjectRequest.builder().bucket(bucket).key(key).contentType("application/json").build(),
                RequestBody.fromBytes(content));
    }

    public String cdnUrl(String key) {
        return cdnBaseUrl + "/" + key;
    }
}
