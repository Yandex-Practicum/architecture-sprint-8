package bionicpro.reports;

import bionicpro.reports.clickhouse.ClickHouseClient;
import bionicpro.reports.handler.HealthHandler;
import bionicpro.reports.handler.ReportHandler;
import bionicpro.reports.s3.S3ReportStore;
import io.javalin.Javalin;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * BionicPRO Report Service.
 * <p>
 * API для получения пользовательских отчётов.
 * Поток: проверка S3 → (если нет) генерация из ClickHouse → сохранение в S3 → ответ с CDN URL.
 * Авторизация: JWT из Authorization header (проксируется через BFF).
 */
public class ReportServer {

    private static final Logger log = LoggerFactory.getLogger(ReportServer.class);

    public static void main(String[] args) {
        // ── Config from env ────────────────────────────────────────────
        int port = intEnv("PORT", 8001);

        // ClickHouse
        String chHost = env("CLICKHOUSE_HOST", "olap_db");
        int chPort = intEnv("CLICKHOUSE_PORT", 8123);

        // MinIO (S3)
        String minioEndpoint = env("MINIO_ENDPOINT", "http://minio:9000");
        String minioAccessKey = env("MINIO_ACCESS_KEY", "minio_user");
        String minioSecretKey = env("MINIO_SECRET_KEY", "minio_password");
        String cdnBaseUrl = env("CDN_BASE_URL", "/cdn");

        // ── Clients ────────────────────────────────────────────────────
        String reportView = System.getenv().getOrDefault("REPORT_VIEW", "user_reports");        
        var ch = new ClickHouseClient(chHost, chPort, reportView);
        var s3 = new S3ReportStore(minioEndpoint, minioAccessKey, minioSecretKey, cdnBaseUrl);

        // ── Handlers ───────────────────────────────────────────────────
        var reportHandler = new ReportHandler(ch, s3);
        var healthHandler = new HealthHandler(ch, s3);

        // ── Server ─────────────────────────────────────────────────────
        var app = Javalin.create(config -> {
            config.showJavalinBanner = false;
        });

        app.get("/reports/me", reportHandler::getMyReport);
        app.get("/reports/{userId}", reportHandler::getReport);
        app.get("/health", healthHandler::check);

        app.start(port);
        log.info("Report Service started on port {}, ClickHouse={}:{}, MinIO={}",
                port, chHost, chPort, minioEndpoint);
    }

    // ── Helpers ────────────────────────────────────────────────────────

    static String env(String key, String defaultValue) {
        String val = System.getenv(key);
        return val != null && !val.isBlank() ? val : defaultValue;
    }

    static int intEnv(String key, int defaultValue) {
        try {
            return Integer.parseInt(System.getenv(key));
        } catch (Exception e) {
            return defaultValue;
        }
    }
}
