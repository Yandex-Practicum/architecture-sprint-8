package bionicpro.reports.handler;

import bionicpro.reports.clickhouse.ClickHouseClient;
import bionicpro.reports.s3.S3ReportStore;
import io.javalin.http.Context;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * GET /health — проверяет доступность ClickHouse и MinIO (S3).
 */
public class HealthHandler {

    private final ClickHouseClient ch;
    private final S3ReportStore s3;

    public HealthHandler(ClickHouseClient ch, S3ReportStore s3) {
        this.ch = ch;
        this.s3 = s3;
    }

    public void check(Context ctx) {
        boolean chOk = ch.ping();
        boolean s3Ok = s3.ping();

        Map<String, Object> body = new LinkedHashMap<>();
        body.put("status", chOk && s3Ok ? "UP" : "DEGRADED");
        body.put("clickhouse", chOk ? "connected" : "unreachable");
        body.put("s3", s3Ok ? "connected" : "unreachable");

        ctx.status(chOk ? 200 : 503).json(body);
    }
}
