package ru.bionicpro.reports.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import io.minio.*;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import ru.bionicpro.reports.config.CdnConfig;
import ru.bionicpro.reports.config.MinioConfig;
import ru.bionicpro.reports.model.ReportResponse;

import java.io.ByteArrayInputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;

@Slf4j
@Service
@RequiredArgsConstructor
public class S3StorageService {

    private final MinioClient minioClient;
    private final MinioConfig minioConfig;
    private final CdnConfig cdnConfig;
    private final ObjectMapper objectMapper;

    private static final DateTimeFormatter DATE_FORMATTER = DateTimeFormatter.ofPattern("yyyy-MM-dd");

    /**
     * Формирование пути к отчёту в S3
     * Формат: user_001/2026-05-27/report_2026-05-27.xml
     */
    private String getReportPath(String userId, LocalDate date, String format) {
        String dateStr = date.format(DATE_FORMATTER);
        return String.format("%s/%s/report_%s.%s", userId, dateStr, dateStr, format.toLowerCase());
    }

    /**
     * Формирование пути к последнему отчёту
     * Формат: user_001/latest.json
     */
    private String getLatestReportPath(String userId, String format) {
        return String.format("%s/latest.%s", userId, format.toLowerCase());
    }

    /**
     * Проверка существования отчёта в S3
     */
    public boolean reportExists(String userId, LocalDate date, String format) {
        String path = getReportPath(userId, date, format);
        try {
            minioClient.statObject(
                    StatObjectArgs.builder()
                            .bucket(minioConfig.getBucket())
                            .object(path)
                            .build()
            );
            log.info("Report exists in S3: {}", path);
            return true;
        } catch (Exception e) {
            log.info("Report not found in S3: {}", path);
            return false;
        }
    }

    /**
     * Получение CDN ссылки на отчёт
     */
    public String getReportUrl(String userId, LocalDate date, String format) {
        String path = getReportPath(userId, date, format);
        return String.format("%s/%s", cdnConfig.getBaseUrl(), path);
    }

    /**
     * Получение CDN ссылки на последний отчёт
     */
    public String getLatestReportUrl(String userId, String format) {
        String path = getLatestReportPath(userId, format);
        return String.format("%s/%s", cdnConfig.getBaseUrl(), path);
    }

    /**
     * Сохранение отчёта в S3
     */
    public void saveReport(String userId, LocalDate date, String format, byte[] content, String contentType) {
        String path = getReportPath(userId, date, format);
        saveToS3(path, content, contentType);

        // Сохраняем как последнюю версию
        String latestPath = getLatestReportPath(userId, format);
        saveToS3(latestPath, content, contentType);
    }

    /**
     * Сохранение JSON отчёта
     */
    public void saveJsonReport(String userId, LocalDate date, ReportResponse report) {
        try {
            byte[] content = objectMapper.writeValueAsBytes(report);
            saveReport(userId, date, "json", content, "application/json");
            log.info("JSON report saved for user: {}, date: {}", userId, date);
        } catch (Exception e) {
            log.error("Error saving JSON report: {}", e.getMessage());
            throw new RuntimeException("Failed to save JSON report", e);
        }
    }

    /**
     * Сохранение XML отчёта
     */
    public void saveXmlReport(String userId, LocalDate date, String xmlContent) {
        byte[] content = xmlContent.getBytes(java.nio.charset.StandardCharsets.UTF_8);
        saveReport(userId, date, "xml", content, "application/xml");
        log.info("XML report saved for user: {}, date: {}", userId, date);
    }

    /**
     * Сохранение CSV отчёта
     */
    public void saveCsvReport(String userId, LocalDate date, byte[] content) {
        saveReport(userId, date, "csv", content, "text/csv");
        log.info("CSV report saved for user: {}, date: {}", userId, date);
    }

    /**
     * Обновление кеша CDN (принудительное обновление)
     */
    public void invalidateCache(String userId, LocalDate date, String format) {
        // В Nginx используется proxy_cache, который автоматически обновляется
        // при истечении TTL. Для принудительного обновления нужно удалить
        // старый отчёт и положить новый с тем же именем
        String path = getReportPath(userId, date, format);
        log.info("Cache invalidation triggered for: {}", path);
        // Nginx сам определит, что файл изменился при следующем запросе
    }

    private void saveToS3(String path, byte[] content, String contentType) {
        try {
            // Проверяем существование bucket
            boolean bucketExists = minioClient.bucketExists(
                    BucketExistsArgs.builder().bucket(minioConfig.getBucket()).build()
            );
            if (!bucketExists) {
                minioClient.makeBucket(
                        MakeBucketArgs.builder().bucket(minioConfig.getBucket()).build()
                );
            }

            // Загружаем файл
            ByteArrayInputStream inputStream = new ByteArrayInputStream(content);
            minioClient.putObject(
                    PutObjectArgs.builder()
                            .bucket(minioConfig.getBucket())
                            .object(path)
                            .stream(inputStream, content.length, -1)
                            .contentType(contentType)
                            .build()
            );
            log.info("File saved to S3: {}", path);
        } catch (Exception e) {
            log.error("Error saving to S3: {}", e.getMessage());
            throw new RuntimeException("Failed to save to S3", e);
        }
    }

    /**
     * Получение статуса кеша через HEAD запрос
     */
    public String getCacheStatus(String url) {
        try {
            HttpURLConnection connection = (HttpURLConnection)
                    new URL(url).openConnection();
            connection.setRequestMethod("HEAD");
            connection.connect();
            return connection.getHeaderField("X-Cache-Status");
        } catch (Exception e) {
            log.warn("Failed to get cache status: {}", e.getMessage());
            return "UNKNOWN";
        }
    }

}
