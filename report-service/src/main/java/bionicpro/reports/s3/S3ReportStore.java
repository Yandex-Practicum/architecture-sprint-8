package bionicpro.reports.s3;

import io.minio.*;
import io.minio.errors.ErrorResponseException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;
import java.util.Optional;

/**
 * Хранилище отчётов в S3 (MinIO).
 * <p>
 * Структура ключей: {@code reports/{userId}/report.json}
 * <p>
 * При запросе отчёта Report Service сначала проверяет S3 (HEAD).
 * Если отчёт есть — возвращает его. Если нет — генерирует из ClickHouse,
 * сохраняет в S3 и возвращает.
 */
public class S3ReportStore {

    private static final Logger log = LoggerFactory.getLogger(S3ReportStore.class);

    private static final String BUCKET = "reports";

    private final MinioClient minio;
    private final String cdnBaseUrl;

    /**
     * @param endpoint   MinIO endpoint (http://minio:9000)
     * @param accessKey  MINIO_ROOT_USER
     * @param secretKey  MINIO_ROOT_PASSWORD
     * @param cdnBaseUrl базовый URL для CDN-ссылок (/cdn)
     */
    public S3ReportStore(String endpoint, String accessKey, String secretKey, String cdnBaseUrl) {
        this.minio = MinioClient.builder()
                .endpoint(endpoint)
                .credentials(accessKey, secretKey)
                .build();
        this.cdnBaseUrl = cdnBaseUrl;

        ensureBucketExists();
    }

    /**
     * Проверяет, существует ли отчёт в S3.
     */
    public boolean exists(int userId) {
        try {
            minio.statObject(StatObjectArgs.builder()
                    .bucket(BUCKET)
                    .object(objectKey(userId))
                    .build());
            return true;
        } catch (ErrorResponseException e) {
            if ("NoSuchKey".equals(e.errorResponse().code())) {
                return false;
            }
            log.error("S3 HEAD error for userId={}: {}", userId, e.getMessage());
            return false;
        } catch (Exception e) {
            log.error("S3 HEAD error for userId={}: {}", userId, e.getMessage());
            return false;
        }
    }

    /**
     * Читает отчёт из S3.
     *
     * @return Optional с JSON-строкой отчёта, или empty если не найден
     */
    public Optional<String> get(int userId) {
        try (var stream = minio.getObject(GetObjectArgs.builder()
                .bucket(BUCKET)
                .object(objectKey(userId))
                .build())) {
            return Optional.of(new String(stream.readAllBytes(), StandardCharsets.UTF_8));
        } catch (ErrorResponseException e) {
            if ("NoSuchKey".equals(e.errorResponse().code())) {
                return Optional.empty();
            }
            log.error("S3 GET error for userId={}: {}", userId, e.getMessage());
            return Optional.empty();
        } catch (Exception e) {
            log.error("S3 GET error for userId={}: {}", userId, e.getMessage());
            return Optional.empty();
        }
    }

    /**
     * Сохраняет отчёт в S3.
     *
     * @param userId     ID пользователя
     * @param reportJson JSON-строка отчёта
     */
    public void put(int userId, String reportJson) {
        try {
            byte[] bytes = reportJson.getBytes(StandardCharsets.UTF_8);
            minio.putObject(PutObjectArgs.builder()
                    .bucket(BUCKET)
                    .object(objectKey(userId))
                    .stream(new ByteArrayInputStream(bytes), bytes.length, -1)
                    .contentType("application/json")
                    .build());
            log.info("Report saved to S3: {}/{}", BUCKET, objectKey(userId));
        } catch (Exception e) {
            log.error("S3 PUT error for userId={}: {}", userId, e.getMessage(), e);
            // Не бросаем исключение — отчёт уже сгенерирован и будет отдан клиенту.
            // S3 — кэширующий слой, его недоступность не должна ломать основной flow.
        }
    }

    /**
     * Формирует CDN URL для отчёта.
     * Nginx проксирует /cdn/reports/... → MinIO /reports/...
     */
    public String cdnUrl(int userId) {
        return cdnBaseUrl + "/reports/" + userId + "/report.json";
    }

    /**
     * Проверяет доступность MinIO.
     */
    public boolean ping() {
        try {
            minio.bucketExists(BucketExistsArgs.builder()
                    .bucket(BUCKET)
                    .build());
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    // ── Internal ───────────────────────────────────────────────────────

    private String objectKey(int userId) {
        return userId + "/report.json";
    }

    private void ensureBucketExists() {
        try {
            boolean exists = minio.bucketExists(BucketExistsArgs.builder()
                    .bucket(BUCKET)
                    .build());
            if (!exists) {
                minio.makeBucket(MakeBucketArgs.builder()
                        .bucket(BUCKET)
                        .build());
                log.info("Created S3 bucket: {}", BUCKET);
            }

            // Установить anonymous read policy для CDN (Nginx)
            String policy = """
                    {
                        "Version": "2012-10-17",
                        "Statement": [{
                            "Effect": "Allow",
                            "Principal": {"AWS": ["*"]},
                            "Action": ["s3:GetObject"],
                            "Resource": ["arn:aws:s3:::%s/*"]
                        }]
                    }
                    """.formatted(BUCKET);
            minio.setBucketPolicy(SetBucketPolicyArgs.builder()
                    .bucket(BUCKET)
                    .config(policy)
                    .build());
            log.info("S3 bucket '{}' configured with anonymous read policy", BUCKET);

        } catch (Exception e) {
            log.warn("Could not ensure S3 bucket exists: {}. "
                    + "Reports will be served from ClickHouse directly.", e.getMessage());
        }
    }
}
