package bionicpro.reports.handler;

import bionicpro.reports.auth.JwtUtil;
import bionicpro.reports.clickhouse.ClickHouseClient;
import bionicpro.reports.s3.S3ReportStore;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.javalin.http.Context;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Обработчик запросов на отчёты с кэшированием в S3.
 * <p>
 * Flow:
 * <ol>
 *   <li>Извлечь userId из JWT</li>
 *   <li>Проверить S3: HEAD reports/{userId}/report.json</li>
 *   <li>Если есть → вернуть из S3 + CDN URL</li>
 *   <li>Если нет → запросить ClickHouse → сохранить в S3 → вернуть + CDN URL</li>
 * </ol>
 * <p>
 * Два endpoint'а:
 * <ul>
 *   <li>{@code GET /reports/me} — userId из JWT (основной, для фронтенда через BFF)</li>
 *   <li>{@code GET /reports/{userId}} — userId из пути (проверка: sub == userId)</li>
 * </ul>
 */
public class ReportHandler {

    private static final Logger log = LoggerFactory.getLogger(ReportHandler.class);
    private static final ObjectMapper mapper = new ObjectMapper();

    private final ClickHouseClient ch;
    private final S3ReportStore s3;

    public ReportHandler(ClickHouseClient ch, S3ReportStore s3) {
        this.ch = ch;
        this.s3 = s3;
    }

    /**
     * GET /reports/me — userId из JWT.
     */
    public void getMyReport(Context ctx) {
        int userId = extractAndValidateToken(ctx);
        if (userId < 0) return;

        fetchAndReturnReport(ctx, userId);
    }

    /**
     * GET /reports/{userId} — проверяет, что sub == userId.
     */
    public void getReport(Context ctx) {
        int tokenUserId = extractAndValidateToken(ctx);
        if (tokenUserId < 0) return;

        String requestedParam = ctx.pathParam("userId");
        int requestedUserId;
        try {
            requestedUserId = Integer.parseInt(requestedParam);
        } catch (NumberFormatException e) {
            ctx.status(400).json(Map.of("error", "userId must be a number"));
            return;
        }

        if (tokenUserId != requestedUserId) {
            log.warn("Access denied: token sub={} requested userId={}",
                    tokenUserId, requestedUserId);
            ctx.status(403).json(Map.of(
                    "error", "Access denied. You can only view your own report."
            ));
            return;
        }

        fetchAndReturnReport(ctx, requestedUserId);
    }

    // ── Core logic ─────────────────────────────────────────────────────

    private void fetchAndReturnReport(Context ctx, int userId) {
        try {
            // ── 1. Проверить S3 ────────────────────────────────────────
            if (s3.exists(userId)) {
                var cached = s3.get(userId);
                if (cached.isPresent()) {
                    log.info("Report served from S3: userId={}", userId);

                    // Парсим JSON из S3 и добавляем cdnUrl
                    Map<String, Object> report = mapper.readValue(
                            cached.get(), new TypeReference<>() {});
                    report.put("cdnUrl", s3.cdnUrl(userId));
                    report.put("source", "s3");

                    ctx.json(report);
                    return;
                }
            }

            // ── 2. Генерировать из ClickHouse ──────────────────────────
            List<Map<String, Object>> rows = ch.queryUserReport(userId);

            if (rows.isEmpty()) {
                ctx.status(404).json(Map.of(
                        "error", "Report not found",
                        "message", "No report available for this user. "
                                + "Reports are generated daily by ETL process."
                ));
                return;
            }

            // ── 3. Сформировать JSON отчёта ────────────────────────────
            Map<String, Object> report = buildReportJson(userId, rows);

            // ── 4. Сохранить в S3 ──────────────────────────────────────
            String reportJson = mapper.writeValueAsString(report);
            s3.put(userId, reportJson);

            // ── 5. Вернуть ответ с CDN URL ─────────────────────────────
            report.put("cdnUrl", s3.cdnUrl(userId));
            report.put("source", "clickhouse");

            ctx.json(report);
            log.info("Report generated and cached: userId={}, prostheses={}",
                    userId, rows.size());

        } catch (Exception e) {
            log.error("Report request failed for userId={}: {}", userId, e.getMessage(), e);
            ctx.status(500).json(Map.of("error", "Internal server error"));
        }
    }

    private Map<String, Object> buildReportJson(int userId, List<Map<String, Object>> rows) {
        String customerName = rows.getFirst().getOrDefault("customer_name", "").toString();
        String customerEmail = rows.getFirst().getOrDefault("customer_email", "").toString();
        String reportUpdated = rows.getFirst().getOrDefault("report_updated", "").toString();

        // LinkedHashMap сохраняет порядок ключей в JSON
        Map<String, Object> report = new LinkedHashMap<>();
        report.put("userId", userId);
        report.put("customerName", customerName);
        report.put("customerEmail", customerEmail);
        report.put("reportUpdated", reportUpdated);
        report.put("prostheses", rows.stream().map(row -> {
            Map<String, Object> p = new LinkedHashMap<>();
            p.put("prosthesisType", row.getOrDefault("prosthesis_type", ""));
            p.put("totalSignals", row.getOrDefault("total_signals", 0));
            p.put("avgAmplitude", row.getOrDefault("avg_amplitude", 0));
            p.put("avgFrequency", row.getOrDefault("avg_frequency", 0));
            p.put("avgDuration", row.getOrDefault("avg_duration", 0));
            p.put("minSignalTime", row.getOrDefault("min_signal_time", ""));
            p.put("maxSignalTime", row.getOrDefault("max_signal_time", ""));
            return p;
        }).toList());

        return report;
    }

    // ── JWT validation ─────────────────────────────────────────────────

    /**
     * Извлекает userId из заголовков, установленных BFF.
     *
     * BFF (ProxyHandler) добавляет:
     * - Authorization: Bearer <token> (для аутентификации)
     * - X-CRM-User-Id: <число> (числовой ID пользователя в CRM)
     *
     * DEMO: CRM ID извлекается из username (prothetic1 → 1).
     * В production: CRM ID должен быть claim в JWT (crm_user_id),
     * заданный через Keycloak User Attribute + Protocol Mapper.
     * Тогда здесь можно парсить его прямо из JWT claims.
     */
    private int extractAndValidateToken(Context ctx) {
        String authHeader = ctx.header("Authorization");
        if (authHeader == null || !authHeader.startsWith("Bearer ")) {
            ctx.status(401).json(Map.of("error", "Missing or invalid Authorization header"));
            return -1;
        }

        // Числовой CRM ID из заголовка BFF
        String crmUserIdHeader = ctx.header("X-CRM-User-Id");
        if (crmUserIdHeader != null) {
            try {
                return Integer.parseInt(crmUserIdHeader);
            } catch (NumberFormatException e) {
                log.warn("Invalid X-CRM-User-Id header: {}", crmUserIdHeader);
            }
        }

        // Fallback: попробовать sub из JWT (если вызов не через BFF)
        String token = authHeader.substring("Bearer ".length());
        Map<String, Object> claims;
        try {
            claims = JwtUtil.parseClaims(token);
        } catch (Exception e) {
            log.warn("Failed to parse JWT: {}", e.getMessage());
            ctx.status(401).json(Map.of("error", "Invalid token"));
            return -1;
        }

        Object subClaim = claims.get("sub");
        if (subClaim == null) {
            ctx.status(401).json(Map.of("error", "Token missing 'sub' claim"));
            return -1;
        }

        try {
            return Integer.parseInt(subClaim.toString());
        } catch (NumberFormatException e) {
            ctx.status(400).json(Map.of(
                    "error", "Cannot determine numeric user ID. "
                    + "JWT sub is UUID; X-CRM-User-Id header not provided."
            ));
            return -1;
        }
    }
}
