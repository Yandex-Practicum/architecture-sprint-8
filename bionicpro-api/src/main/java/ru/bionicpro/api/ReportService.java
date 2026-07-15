package ru.bionicpro.api;

import org.springframework.r2dbc.core.DatabaseClient;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Flux;

import java.time.LocalDate;

@Component
public final class ReportService {

    private final DatabaseClient databaseClient;

    public ReportService(DatabaseClient databaseClient) {
        this.databaseClient = databaseClient;
    }

    public Flux<ReportEntry> findAllByUserId(String userId) {
        return databaseClient.sql("""
                        SELECT report_date, prosthesis_serial, total_movements, avg_response_ms, active_hours
                        FROM prosthesis_report
                        WHERE user_id = :userId
                        """)
                .bind("userId", userId)
                .map((row, rowMetadata) -> new ReportEntry(
                        row.get("report_date", LocalDate.class),
                        row.get("prosthesis_serial", String.class),
                        row.get("total_movements", Long.class),
                        row.get("avg_response_ms", Double.class),
                        row.get("active_hours", Double.class)
                ))
                .all();
    }

}
