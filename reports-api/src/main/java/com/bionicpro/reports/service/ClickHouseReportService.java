package com.bionicpro.reports.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.Optional;

@Service
public class ClickHouseReportService {

    private static final DateTimeFormatter CLICKHOUSE_DATETIME = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    private static final String COLUMNS = """
            username, first_name, last_name, prosthetic_id, country,
            toString(period_start) AS period_start_iso, toString(period_end) AS period_end_iso,
            events_count, avg_latency_ms, avg_signal_quality
            """;

    private final RestClient restClient;
    private final ObjectMapper objectMapper = new ObjectMapper();
    private final String martTable;

    public ClickHouseReportService(@Value("${bionicpro.clickhouse-url}") String clickhouseUrl,
                                    @Value("${bionicpro.mart-table:reports.customer_mart}") String martTable) {
        this.restClient = RestClient.builder().baseUrl(clickhouseUrl).build();
        this.martTable = martTable;
    }

    public Optional<CustomerMartRow> latestReportFor(String username) {
        String query = ("SELECT " + COLUMNS + """
                FROM %s
                WHERE username = {username:String}
                ORDER BY period_start DESC
                LIMIT 1
                FORMAT JSONEachRow
                """).formatted(martTable);

        String body = restClient.post()
                .uri(uriBuilder -> uriBuilder.queryParam("param_username", username).build())
                .body(query)
                .retrieve()
                .body(String.class);

        return parseFirstRow(body);
    }

    public Optional<CustomerMartRow> reportFor(String username, LocalDateTime periodStart) {
        String query = ("SELECT " + COLUMNS + """
                FROM %s
                WHERE username = {username:String} AND period_start = {periodStart:DateTime}
                LIMIT 1
                FORMAT JSONEachRow
                """).formatted(martTable);

        String body = restClient.post()
                .uri(uriBuilder -> uriBuilder
                        .queryParam("param_username", username)
                        .queryParam("param_periodStart", periodStart.format(CLICKHOUSE_DATETIME))
                        .build())
                .body(query)
                .retrieve()
                .body(String.class);

        return parseFirstRow(body);
    }

    private Optional<CustomerMartRow> parseFirstRow(String body) {
        if (body == null || body.isBlank()) {
            return Optional.empty();
        }
        String firstLine = body.lines().findFirst().orElse(null);
        if (firstLine == null || firstLine.isBlank()) {
            return Optional.empty();
        }

        JsonNode row;
        try {
            row = objectMapper.readTree(firstLine);
        } catch (Exception e) {
            throw new IllegalStateException("Unparsable ClickHouse response: " + firstLine, e);
        }
        return Optional.of(new CustomerMartRow(
                row.path("username").asText(),
                row.path("first_name").asText(),
                row.path("last_name").asText(),
                row.path("prosthetic_id").asText(),
                row.path("country").asText(),
                row.path("period_start_iso").asText(),
                row.path("period_end_iso").asText(),
                row.path("events_count").asInt(),
                row.path("avg_latency_ms").asDouble(),
                row.path("avg_signal_quality").asDouble()));
    }
}
