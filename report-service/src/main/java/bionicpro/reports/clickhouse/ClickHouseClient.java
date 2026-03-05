package bionicpro.reports.clickhouse;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.List;
import java.util.Map;

/**
 * HTTP-клиент для ClickHouse.
 * <p>
 * Использует HTTP-интерфейс ClickHouse (порт 8123) и встроенный
 * {@link java.net.http.HttpClient} — никаких дополнительных зависимостей.
 * Запросы возвращаются в формате JSON.
 * <p>
 * Витрина для отчётов задаётся через параметр {@code reportView}:
 * <ul>
 *   <li>{@code user_reports} — batch-витрина из Airflow ETL (задание 2)</li>
 *   <li>{@code user_reports_cdc} — CDC-витрина из Debezium pipeline (задание 4)</li>
 * </ul>
 */
public class ClickHouseClient {

    private static final Logger log = LoggerFactory.getLogger(ClickHouseClient.class);
    private static final ObjectMapper mapper = new ObjectMapper();

    /** Витрина по умолчанию — batch ETL из задания 2. */
    private static final String DEFAULT_REPORT_VIEW = "user_reports";

    private final String baseUrl;
    private final String reportView;
    private final HttpClient http;

    public ClickHouseClient(String host, int port) {
        this(host, port, DEFAULT_REPORT_VIEW);
    }

    /**
     * @param host       hostname ClickHouse (e.g. "olap_db")
     * @param port       HTTP-порт (e.g. 8123)
     * @param reportView имя витрины: "user_reports" или "user_reports_cdc"
     */
    public ClickHouseClient(String host, int port, String reportView) {
        this.baseUrl = "http://" + host + ":" + port;
        this.reportView = (reportView != null && !reportView.isBlank())
                ? reportView : DEFAULT_REPORT_VIEW;
        this.http = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(5))
                .build();
        log.info("ClickHouseClient initialized: url={}, reportView={}", baseUrl, this.reportView);
    }

    /**
     * Проверяет доступность ClickHouse.
     */
    public boolean ping() {
        try {
            var req = HttpRequest.newBuilder()
                    .uri(URI.create(baseUrl + "/ping"))
                    .timeout(Duration.ofSeconds(3))
                    .GET()
                    .build();
            var resp = http.send(req, HttpResponse.BodyHandlers.ofString());
            return resp.statusCode() == 200;
        } catch (Exception e) {
            log.warn("ClickHouse ping failed: {}", e.getMessage());
            return false;
        }
    }

    /**
     * Запрашивает отчёт по userId из витрины (batch или CDC).
     * <p>
     * Обе витрины возвращают одинаковую структуру колонок:
     * user_id, customer_name, customer_email, prosthesis_type,
     * total_signals, avg_amplitude, avg_frequency, avg_duration,
     * min_signal_time, max_signal_time, report_updated.
     * <p>
     * Параметр userId передаётся безопасно — через числовой каст,
     * SQL-инъекция невозможна (int, не строка).
     *
     * @param userId числовой ID пользователя
     * @return список Map-ов с данными отчёта (может быть пустым)
     */
    public List<Map<String, Object>> queryUserReport(int userId) throws Exception {
        String sql = """
                SELECT
                    user_id,
                    customer_name,
                    customer_email,
                    prosthesis_type,
                    total_signals,
                    avg_amplitude,
                    avg_frequency,
                    avg_duration,
                    toString(min_signal_time) AS min_signal_time,
                    toString(max_signal_time) AS max_signal_time,
                    toString(report_updated)  AS report_updated
                FROM %s
                WHERE user_id = %d
                ORDER BY prosthesis_type
                FORMAT JSON
                """.formatted(reportView, userId);

        String responseBody = executeQuery(sql);

        // ClickHouse FORMAT JSON возвращает: { "data": [...], "rows": N, ... }
        Map<String, Object> envelope = mapper.readValue(responseBody,
                new TypeReference<>() {});

        Object data = envelope.get("data");
        if (data == null) {
            return List.of();
        }

        @SuppressWarnings("unchecked")
        List<Map<String, Object>> rows = (List<Map<String, Object>>) data;
        return rows;
    }

    /** Возвращает имя используемой витрины (для /health endpoint). */
    public String getReportView() {
        return reportView;
    }

    // ── Internal ───────────────────────────────────────────────────────

    private String executeQuery(String sql) throws Exception {
        var req = HttpRequest.newBuilder()
                .uri(URI.create(baseUrl + "/"))
                .timeout(Duration.ofSeconds(30))
                .header("Content-Type", "text/plain; charset=utf-8")
                .POST(HttpRequest.BodyPublishers.ofString(sql))
                .build();

        var resp = http.send(req, HttpResponse.BodyHandlers.ofString());

        if (resp.statusCode() != 200) {
            String body = resp.body();
            log.error("ClickHouse error (HTTP {}): {}", resp.statusCode(), body);
            throw new RuntimeException("ClickHouse query failed: " + body);
        }

        return resp.body();
    }
}
