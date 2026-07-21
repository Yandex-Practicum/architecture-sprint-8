// Package reports builds a per-user prosthesis report by reading the
// pre-aggregated mart from ClickHouse. No heavy computation happens here at
// request time — the ETL (Airflow) already produced the mart.
package reports

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"

	"github.com/bionicpro/reports-api/internal/clickhouse"
)

// DailyMetric is one day of aggregated telemetry for a user.
type DailyMetric struct {
	Date             string  `json:"date"`
	TelemetryEvents  uint64  `json:"telemetry_events"`
	AvgResponseMs    float64 `json:"avg_response_ms"`
	MaxResponseMs    float64 `json:"max_response_ms"`
	AvgSignalQuality float64 `json:"avg_signal_quality"`
	TotalMovements   uint64  `json:"total_movements"`
	AvgBatteryPct    float64 `json:"avg_battery_pct"`
}

// Summary aggregates the whole reporting window.
type Summary struct {
	Days           int     `json:"days"`
	TotalEvents    uint64  `json:"total_telemetry_events"`
	TotalMovements uint64  `json:"total_movements"`
	AvgResponseMs  float64 `json:"avg_response_ms"`
}

// Report is the response returned for a single user.
type Report struct {
	Username            string        `json:"username"`
	FullName            string        `json:"full_name,omitempty"`
	ProsthesisSerial    string        `json:"prosthesis_serial,omitempty"`
	Region              string        `json:"region,omitempty"`
	LatestProcessedDate string        `json:"latest_processed_date"`
	RequestedFrom       string        `json:"requested_from,omitempty"`
	RequestedTo         string        `json:"requested_to,omitempty"`
	Notice              string        `json:"notice,omitempty"`
	Days                []DailyMetric `json:"days"`
	Summary             Summary       `json:"summary"`
}

// Builder reads reports from a ClickHouse mart.
type Builder struct {
	ch    *clickhouse.Client
	db    string
	table string
	// useFinal appends the FINAL modifier. Needed for a *MergeTree mart (the
	// Airflow batch mart), but must be off when the mart is a plain VIEW (the
	// CDC витрина), where FINAL is not allowed.
	useFinal bool
}

// NewBuilder wires the report builder to a ClickHouse table.
func NewBuilder(ch *clickhouse.Client, db, table string, useFinal bool) *Builder {
	return &Builder{ch: ch, db: db, table: table, useFinal: useFinal}
}

func (b *Builder) source() string {
	src := b.db + "." + b.table
	if b.useFinal {
		src += " FINAL"
	}
	return src
}

type chRow struct {
	Date             string  `json:"date"`
	TelemetryEvents  uint64  `json:"telemetry_events"`
	AvgResponseMs    float64 `json:"avg_response_ms"`
	MaxResponseMs    float64 `json:"max_response_ms"`
	AvgSignalQuality float64 `json:"avg_signal_quality"`
	TotalMovements   uint64  `json:"total_movements"`
	AvgBatteryPct    float64 `json:"avg_battery_pct"`
	FullName         string  `json:"full_name"`
	ProsthesisSerial string  `json:"prosthesis_serial"`
	Region           string  `json:"region"`
}

type chEnvelope struct {
	Data []json.RawMessage `json:"data"`
}

// Build returns the report for username, optionally bounded to [from, to]
// (inclusive, YYYY-MM-DD). Only data already loaded into the mart by Airflow is
// returned; a request that reaches beyond the latest processed date is served
// with whatever exists and a notice.
func (b *Builder) Build(ctx context.Context, username, from, to string) (*Report, error) {
	qualified := b.db + "." + b.table

	// 1) latest processed date across the whole mart (the Airflow watermark).
	latest, err := b.latestProcessedDate(ctx, qualified)
	if err != nil {
		return nil, err
	}

	// 2) the user's daily rows within the requested window.
	var where strings.Builder
	where.WriteString("WHERE username = {user:String}")
	params := map[string]string{"user": username}
	if from != "" {
		where.WriteString(" AND report_date >= {from:Date}")
		params["from"] = from
	}
	if to != "" {
		where.WriteString(" AND report_date <= {to:Date}")
		params["to"] = to
	}

	query := fmt.Sprintf(`SELECT
    toString(report_date) AS date,
    telemetry_events,
    round(avg_response_ms, 2) AS avg_response_ms,
    max_response_ms,
    round(avg_signal_quality, 4) AS avg_signal_quality,
    total_movements,
    round(avg_battery_pct, 2) AS avg_battery_pct,
    full_name,
    prosthesis_serial,
    region
FROM %s
%s
ORDER BY report_date`, b.source(), where.String())

	body, err := b.ch.QueryJSON(ctx, query, params)
	if err != nil {
		return nil, err
	}
	var env chEnvelope
	if err := json.Unmarshal(body, &env); err != nil {
		return nil, fmt.Errorf("decode clickhouse response: %w", err)
	}

	report := &Report{
		Username:            username,
		LatestProcessedDate: latest,
		RequestedFrom:       from,
		RequestedTo:         to,
		Days:                make([]DailyMetric, 0, len(env.Data)),
	}
	for _, raw := range env.Data {
		var r chRow
		if err := json.Unmarshal(raw, &r); err != nil {
			return nil, fmt.Errorf("decode row: %w", err)
		}
		if report.FullName == "" {
			report.FullName = r.FullName
			report.ProsthesisSerial = r.ProsthesisSerial
			report.Region = r.Region
		}
		report.Days = append(report.Days, DailyMetric{
			Date:             r.Date,
			TelemetryEvents:  r.TelemetryEvents,
			AvgResponseMs:    r.AvgResponseMs,
			MaxResponseMs:    r.MaxResponseMs,
			AvgSignalQuality: r.AvgSignalQuality,
			TotalMovements:   r.TotalMovements,
			AvgBatteryPct:    r.AvgBatteryPct,
		})
		report.Summary.TotalEvents += r.TelemetryEvents
		report.Summary.TotalMovements += r.TotalMovements
	}
	report.Summary.Days = len(report.Days)
	report.Summary.AvgResponseMs = weightedAvgResponse(report.Days)

	// The user asked for data past what Airflow has processed.
	if to != "" && latest != "" && to > latest {
		report.Notice = fmt.Sprintf("data is available only up to %s (already processed by the ETL); the requested end date %s is not yet in the OLAP store", latest, to)
	}
	return report, nil
}

// Watermark returns the latest date already processed by the ETL (max
// report_date across the mart), used to version the report cache key.
func (b *Builder) Watermark(ctx context.Context) (string, error) {
	return b.latestProcessedDate(ctx, b.db+"."+b.table)
}

func (b *Builder) latestProcessedDate(ctx context.Context, qualified string) (string, error) {
	body, err := b.ch.QueryJSON(ctx,
		fmt.Sprintf("SELECT toString(max(report_date)) AS latest FROM %s", qualified), nil)
	if err != nil {
		return "", err
	}
	var env struct {
		Data []struct {
			Latest string `json:"latest"`
		} `json:"data"`
	}
	if err := json.Unmarshal(body, &env); err != nil {
		return "", fmt.Errorf("decode watermark: %w", err)
	}
	if len(env.Data) == 0 {
		return "", nil
	}
	return env.Data[0].Latest, nil
}

// weightedAvgResponse averages the daily averages weighted by event count.
func weightedAvgResponse(days []DailyMetric) float64 {
	var num float64
	var den uint64
	for _, d := range days {
		num += d.AvgResponseMs * float64(d.TelemetryEvents)
		den += d.TelemetryEvents
	}
	if den == 0 {
		return 0
	}
	return num / float64(den)
}
