package ru.reports.api.repository;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;
import ru.reports.api.response.ProstheticReportResponse;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

@Repository
public class ReportRepository {


    private final JdbcClient jdbcClient;

    public ReportRepository(JdbcClient jdbcClient) {
        this.jdbcClient = jdbcClient;
    }

    public List<ProstheticReportResponse> findByUserIdAndPeriod(
            String userId,
            LocalDate from,
            LocalDate to
    ) {
        return jdbcClient.sql("""
                    SELECT
                        user_id AS userId,
                        prosthetic_id AS prostheticId,
                        report_date AS reportDate,
                        user_full_name AS userFullName,
                        prosthetic_model AS prostheticModel,
                        serial_number AS serialNumber,
                        total_events AS totalEvents,
                        avg_response_time_ms AS avgResponseTimeMs,
                        max_response_time_ms AS maxResponseTimeMs,
                        avg_sensor_noise AS avgSensorNoise,
                        low_battery_events AS lowBatteryEvents,
                        last_telemetry_at AS lastTelemetryAt,
                        updated_at AS updatedAt
                    FROM reports.user_prosthetic_report_mart
                    WHERE user_id = :userId
                      AND report_date BETWEEN :from AND :to
                    ORDER BY report_date DESC, prosthetic_id
                    """)
                .param("userId", userId)
                .param("from", from)
                .param("to", to)
                .query(ProstheticReportResponse.class)
                .list();
    }

    public Optional<LocalDate> findMaxProcessedDateByUserId(String userId) {
        return jdbcClient.sql("""
                    SELECT max(report_date)
                    FROM reports.user_prosthetic_report_mart
                    WHERE user_id = :userId
                    """)
                .param("userId", userId)
                .query(LocalDate.class)
                .optional();
    }
}

