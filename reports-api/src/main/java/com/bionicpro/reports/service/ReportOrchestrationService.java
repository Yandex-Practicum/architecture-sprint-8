package com.bionicpro.reports.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Service;

import java.nio.charset.StandardCharsets;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.time.temporal.ChronoUnit;
import java.util.Optional;

@Service
public class ReportOrchestrationService {

    private static final DateTimeFormatter KEY_FORMAT = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH-mm-ss");

    private final ClickHouseReportService clickHouseReportService;
    private final ReportStorageService storageService;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public ReportOrchestrationService(ClickHouseReportService clickHouseReportService,
                                       ReportStorageService storageService) {
        this.clickHouseReportService = clickHouseReportService;
        this.storageService = storageService;
    }

    public Optional<String> resolveReportUrl(String username) {
        LocalDateTime expectedPeriod = LocalDateTime.now(ZoneOffset.UTC).truncatedTo(ChronoUnit.HOURS).minusHours(1);
        String expectedKey = keyFor(username, expectedPeriod);

        if (storageService.exists(expectedKey)) {
            return Optional.of(storageService.cdnUrl(expectedKey));
        }

        Optional<CustomerMartRow> row = clickHouseReportService.reportFor(username, expectedPeriod);
        if (row.isEmpty()) {
            row = clickHouseReportService.latestReportFor(username);
        }
        if (row.isEmpty()) {
            return Optional.empty();
        }

        String key = keyFor(username, row.get().periodStart());
        if (!storageService.exists(key)) {
            storageService.put(key, serialize(row.get()));
        }
        return Optional.of(storageService.cdnUrl(key));
    }

    private String keyFor(String username, LocalDateTime periodStart) {
        return keyFor(username, periodStart.format(KEY_FORMAT));
    }

    private String keyFor(String username, String periodStartRaw) {
        String normalized = periodStartRaw.contains(" ")
                ? LocalDateTime.parse(periodStartRaw.replace(" ", "T")).format(KEY_FORMAT)
                : periodStartRaw;
        return "reports/%s/%s.json".formatted(username, normalized);
    }

    private byte[] serialize(CustomerMartRow row) {
        try {
            return objectMapper.writeValueAsBytes(row);
        } catch (Exception e) {
            throw new IllegalStateException("Failed to serialize report", e);
        }
    }
}
