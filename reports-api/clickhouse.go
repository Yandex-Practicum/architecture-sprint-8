package main

import (
	"context"
	"errors"

	"github.com/ClickHouse/clickhouse-go/v2"
	"github.com/ClickHouse/clickhouse-go/v2/lib/driver"
)

const (
	chUnknownTable    = 60
	chUnknownDatabase = 81
)

type mart struct {
	conn driver.Conn
}

type reportRow struct {
	ReportDate      string  `ch:"report_date" json:"report_date"`
	FullName        string  `ch:"full_name" json:"full_name"`
	ProsthesisModel string  `ch:"prosthesis_model" json:"prosthesis_model"`
	SignalsCount    uint64  `ch:"signals_count" json:"signals_count"`
	MovementsCount  uint64  `ch:"movements_count" json:"movements_count"`
	AvgReactionMs   float64 `ch:"avg_reaction_ms" json:"avg_reaction_ms"`
	AvgBatteryLevel float64 `ch:"avg_battery_level" json:"avg_battery_level"`
}

func openMart(addr, database string) (*mart, error) {
	conn, err := clickhouse.Open(&clickhouse.Options{
		Addr: []string{addr},
		Auth: clickhouse.Auth{Database: database, Username: "default"},
	})
	if err != nil {
		return nil, err
	}
	return &mart{conn: conn}, nil
}

func (m *mart) processedUpTo(ctx context.Context) (string, error) {
	var (
		total uint64
		last  string
	)
	query := "SELECT count(), toString(max(report_date)) FROM user_reports"
	if err := m.conn.QueryRow(ctx, query).Scan(&total, &last); err != nil {
		if isMissingMart(err) {
			return "", nil
		}
		return "", err
	}
	if total == 0 {
		return "", nil
	}
	return last, nil
}

func (m *mart) reportRows(ctx context.Context, userID, from, to string) ([]reportRow, error) {
	query := `
		SELECT toString(report_date) AS report_date, full_name, prosthesis_model,
		       signals_count, movements_count, avg_reaction_ms, avg_battery_level
		FROM user_reports
		WHERE user_id = ? AND user_reports.report_date BETWEEN toDate(?) AND toDate(?)
		ORDER BY user_reports.report_date`

	rows := []reportRow{}
	if err := m.conn.Select(ctx, &rows, query, userID, from, to); err != nil {
		return nil, err
	}
	return rows, nil
}

func isMissingMart(err error) bool {
	var ex *clickhouse.Exception
	if !errors.As(err, &ex) {
		return false
	}
	return ex.Code == chUnknownTable || ex.Code == chUnknownDatabase
}
