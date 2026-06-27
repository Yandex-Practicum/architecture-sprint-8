import { createClient } from '@clickhouse/client';
import { config } from './config.js';

export const clickhouse = createClient({
  url: config.clickhouse.url,
  username: config.clickhouse.username,
  password: config.clickhouse.password,
  database: config.clickhouse.database,
});

export function defaultDateRange(now = new Date()) {
  const to = now.toISOString().slice(0, 10);
  const fromDate = new Date(now);
  fromDate.setUTCDate(fromDate.getUTCDate() - 30);

  return {
    from: fromDate.toISOString().slice(0, 10),
    to,
  };
}

export function normalizeDateRange(query) {
  const defaults = defaultDateRange();
  const from = query.from || defaults.from;
  const to = query.to || defaults.to;

  if (!/^\d{4}-\d{2}-\d{2}$/.test(from) || !/^\d{4}-\d{2}-\d{2}$/.test(to)) {
    const error = new Error('Date filters must use YYYY-MM-DD format');
    error.statusCode = 400;
    throw error;
  }

  if (from > to) {
    const error = new Error('The "from" date must be before or equal to "to"');
    error.statusCode = 400;
    throw error;
  }

  return { from, to };
}

export async function getReportRows({ userId, from, to }) {
  const resultSet = await clickhouse.query({
    query: `
      SELECT
        report_date,
        user_id,
        client_id,
        prosthesis_id,
        full_name,
        email,
        country,
        prosthesis_model,
        events_count,
        active_minutes,
        avg_response_ms,
        p95_response_ms,
        avg_battery_percent,
        min_battery_percent,
        avg_signal_quality,
        error_events,
        last_event_at,
        mart_updated_at
      FROM report_user_prosthesis_daily
      WHERE user_id = {userId:String}
        AND report_date >= {from:Date}
        AND report_date <= {to:Date}
      ORDER BY report_date DESC, prosthesis_id
    `,
    query_params: {
      userId,
      from,
      to,
    },
    format: 'JSONEachRow',
  });

  return resultSet.json();
}
