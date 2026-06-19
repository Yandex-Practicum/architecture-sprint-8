package ru.reports.api.response;

import java.time.LocalDate;
import java.time.LocalDateTime;

public record ProstheticReportResponse(
        String userId,
        String prostheticId,
        LocalDate reportDate,

        String userFullName,
        String prostheticModel,
        String serialNumber,

        long totalEvents,
        double avgResponseTimeMs,
        double maxResponseTimeMs,
        double avgSensorNoise,
        long lowBatteryEvents,

        LocalDateTime lastTelemetryAt,
        LocalDateTime updatedAt
) {
}