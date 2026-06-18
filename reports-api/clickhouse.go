package main

import (
	"context"
	"fmt"
	"log"
	"time"

	"github.com/ClickHouse/clickhouse-go/v2"
	"github.com/ClickHouse/clickhouse-go/v2/lib/driver"
)

type clickhouseClient struct {
	conn driver.Conn
	db   string
}

type reportRow struct {
	UserID              uint64    `ch:"user_id"`
	UserEmail           string    `ch:"user_email"`
	UserFirstName       string    `ch:"user_first_name"`
	UserLastName        string    `ch:"user_last_name"`
	UserCountry         string    `ch:"user_country"`
	ProsthesisID        uint64    `ch:"prosthesis_id"`
	ProsthesisModel     string    `ch:"prosthesis_model"`
	ProsthesisSerial    string    `ch:"prosthesis_serial"`
	ReportDate          time.Time `ch:"report_date"`
	SessionsCount       uint32    `ch:"sessions_count"`
	TotalActiveMinutes  uint32    `ch:"total_active_minutes"`
	AvgSignalStrength   float32   `ch:"avg_signal_strength"`
	MaxSignalStrength   float32   `ch:"max_signal_strength"`
	ErrorEventsCount    uint32    `ch:"error_events_count"`
	BatteryAvgPercent   float32   `ch:"battery_avg_percent"`
	ActuatorCyclesTotal uint64    `ch:"actuator_cycles_total"`
}

func newClickhouseClient(cfg config) (*clickhouseClient, error) {
	conn, err := clickhouse.Open(&clickhouse.Options{
		Addr: []string{fmt.Sprintf("%s:%d", cfg.ClickhouseHost, cfg.ClickhousePort)},
		Auth: clickhouse.Auth{
			Database: cfg.ClickhouseDB,
			Username: cfg.ClickhouseUser,
			Password: cfg.ClickhousePassword,
		},
		DialTimeout:     5 * time.Second,
		MaxOpenConns:    10,
		MaxIdleConns:    5,
		ConnMaxLifetime: time.Hour,
	})
	if err != nil {
		return nil, fmt.Errorf("clickhouse open: %w", err)
	}
	return &clickhouseClient{conn: conn, db: cfg.ClickhouseDB}, nil
}

func (c *clickhouseClient) close() error {
	return c.conn.Close()
}

func (c *clickhouseClient) ping(ctx context.Context) error {
	return c.conn.Ping(ctx)
}

func waitForClickhouse(ch *clickhouseClient) error {
	const maxAttempts = 30
	const delay = 3 * time.Second
	for i := 1; i <= maxAttempts; i++ {
		ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
		err := ch.ping(ctx)
		cancel()
		if err == nil {
			return nil
		}
		log.Printf("clickhouse not ready (attempt %d/%d): %v", i, maxAttempts, err)
		time.Sleep(delay)
	}
	return fmt.Errorf("clickhouse unreachable after %d attempts", maxAttempts)
}

func (c *clickhouseClient) userReport(
	ctx context.Context,
	userID uint64,
	from, to time.Time,
) ([]reportRow, error) {
	const q = `
		SELECT user_id, user_email, user_first_name, user_last_name, user_country,
		       prosthesis_id, prosthesis_model, prosthesis_serial, report_date,
		       sessions_count, total_active_minutes,
		       avg_signal_strength, max_signal_strength, error_events_count,
		       battery_avg_percent, actuator_cycles_total
		FROM prosthesis_user_report
		WHERE user_id = ?
		  AND report_date >= ?
		  AND report_date <= ?
		ORDER BY report_date, prosthesis_id
	`
	rows, err := c.conn.Query(ctx, q, userID, from, to)
	if err != nil {
		return nil, fmt.Errorf("clickhouse query: %w", err)
	}
	defer rows.Close()

	var out []reportRow
	for rows.Next() {
		var r reportRow
		if err := rows.ScanStruct(&r); err != nil {
			return nil, fmt.Errorf("clickhouse scan: %w", err)
		}
		out = append(out, r)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("clickhouse rows: %w", err)
	}
	return out, nil
}