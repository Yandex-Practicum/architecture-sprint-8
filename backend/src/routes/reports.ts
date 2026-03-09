import { Response, Router } from 'express';
import { Pool } from 'pg';
import { AuthenticatedRequest } from '../middleware/auth';

const router = Router();

const pool = new Pool({
  host: process.env.OLAP_DB_HOST ?? 'localhost',
  port: parseInt(process.env.OLAP_DB_PORT ?? '5432', 10),
  database: process.env.OLAP_DB_NAME ?? 'olap',
  user: process.env.OLAP_DB_USER ?? 'clients',
  password: process.env.OLAP_DB_PASSWORD ?? 'olap',
});

/**
 * GET /reports
 *
 * Задача 4: Ограничение доступа.
 * Идентификатор пользователя извлекается из JWT (email из claims Keycloak).
 * Запрос к БД выполняется строго по этому email — пользователь не может
 * запросить данные другого пользователя, так как параметр не принимается
 * извне, а берётся только из верифицированного токена.
 */
router.get('/', async (req: AuthenticatedRequest, res: Response): Promise<void> => {
  const userEmail = req.user?.email;

  // email является стандартным OIDC-клеймом; без него отчёт недоступен
  if (!userEmail) {
    res.status(403).json({
      error: 'Forbidden: email claim missing in token. Configure Keycloak to include email scope.',
    });
    return;
  }

  try {
    // Запрос к OLAP-витрине — только строки с email текущего пользователя.
    // Никакой дополнительной проверки не нужно: SQL-параметр $1 берётся
    // исключительно из JWT, а не из запроса клиента.
    const result = await pool.query<Record<string, unknown>>(
      `SELECT
        client_id,
        report_date,
        full_name,
        email,
        segment,
        region,
        contract_active,
        events_total,
        events_distinct_devices,
        value_sum,
        value_avg,
        value_min,
        value_max,
        first_event_ts,
        last_event_ts,
        updated_at
      FROM mart.user_reports
      WHERE email = $1
      ORDER BY report_date DESC`,
      [userEmail]
    );

    if (result.rows.length === 0) {
      res.status(404).json({ error: 'No report found for this user' });
      return;
    }

    const csv = rowsToCsv(result.rows);

    const filename = `report_${userEmail}_${new Date().toISOString().slice(0, 10)}.csv`;
    res.setHeader('Content-Type', 'text/csv; charset=utf-8');
    res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
    res.send(csv);
  } catch (err) {
    console.error('Database query error:', err);
    res.status(500).json({ error: 'Internal server error' });
  }
});

/**
 * POST /reports/generate
 *
 * Запускает генерацию отчёта для текущего пользователя:
 * читает staging.crm_clients + staging.telemetry_raw и делает UPSERT
 * в mart.user_reports — только для строки с email из JWT.
 *
 * Задача 4: пользователь не передаёт никакого идентификатора —
 * email берётся исключительно из верифицированного токена.
 */
router.post('/generate', async (req: AuthenticatedRequest, res: Response): Promise<void> => {
  const userEmail = req.user?.email;

  if (!userEmail) {
    res.status(403).json({
      error: 'Forbidden: email claim missing in token.',
    });
    return;
  }

  try {
    const result = await pool.query<{ rows_upserted: string }>(
      `WITH aggregated AS (
        SELECT
          c.client_id,
          CURRENT_DATE - 1                                       AS report_date,
          c.full_name,
          c.email,
          c.segment,
          c.region,
          (
            c.contract_start <= CURRENT_DATE
            AND (c.contract_end IS NULL OR c.contract_end >= CURRENT_DATE)
          )                                                      AS contract_active,
          COALESCE(t.events_total, 0)                            AS events_total,
          COALESCE(t.events_distinct_devices, 0)                 AS events_distinct_devices,
          t.value_sum,
          t.value_avg,
          t.value_min,
          t.value_max,
          t.first_event_ts,
          t.last_event_ts
        FROM staging.crm_clients c
        LEFT JOIN (
          SELECT
            client_id,
            COUNT(*)                   AS events_total,
            COUNT(DISTINCT device_id)  AS events_distinct_devices,
            SUM(value)                 AS value_sum,
            AVG(value)                 AS value_avg,
            MIN(value)                 AS value_min,
            MAX(value)                 AS value_max,
            MIN(event_ts)              AS first_event_ts,
            MAX(event_ts)              AS last_event_ts
          FROM staging.telemetry_raw
          WHERE event_ts::DATE = CURRENT_DATE - 1
          GROUP BY client_id
        ) t ON t.client_id = c.client_id
        WHERE c.email = $1
      ),
      upserted AS (
        INSERT INTO mart.user_reports (
          client_id, report_date, full_name, email, segment, region,
          contract_active, events_total, events_distinct_devices,
          value_sum, value_avg, value_min, value_max,
          first_event_ts, last_event_ts, updated_at
        )
        SELECT
          client_id, report_date, full_name, email, segment, region,
          contract_active, events_total, events_distinct_devices,
          value_sum, value_avg, value_min, value_max,
          first_event_ts, last_event_ts, NOW()
        FROM aggregated
        ON CONFLICT (client_id, report_date) DO UPDATE SET
          full_name               = EXCLUDED.full_name,
          segment                 = EXCLUDED.segment,
          region                  = EXCLUDED.region,
          contract_active         = EXCLUDED.contract_active,
          events_total            = EXCLUDED.events_total,
          events_distinct_devices = EXCLUDED.events_distinct_devices,
          value_sum               = EXCLUDED.value_sum,
          value_avg               = EXCLUDED.value_avg,
          value_min               = EXCLUDED.value_min,
          value_max               = EXCLUDED.value_max,
          first_event_ts          = EXCLUDED.first_event_ts,
          last_event_ts           = EXCLUDED.last_event_ts,
          updated_at              = NOW()
        RETURNING 1
      )
      SELECT COUNT(*) AS rows_upserted FROM upserted`,
      [userEmail]
    );

    const rowsUpserted = parseInt(result.rows[0]?.rows_upserted ?? '0', 10);
    res.status(200).json({
      message: 'Report generated successfully',
      rows_upserted: rowsUpserted,
      report_date: new Date(Date.now() - 86400000).toISOString().slice(0, 10),
    });
  } catch (err) {
    console.error('Report generation error:', err);
    res.status(500).json({ error: 'Internal server error during report generation' });
  }
});

function rowsToCsv(rows: Record<string, unknown>[]): string {
  if (rows.length === 0) return '';
  const headers = Object.keys(rows[0]);
  const escape = (val: unknown): string => {
    if (val === null || val === undefined) return '';
    const s = String(val);
    return s.includes(',') || s.includes('"') || s.includes('\n')
      ? `"${s.replace(/"/g, '""')}"`
      : s;
  };
  const lines = [
    headers.join(','),
    ...rows.map((row) => headers.map((h) => escape(row[h])).join(',')),
  ];
  return lines.join('\n');
}

export default router;
