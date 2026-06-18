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
	UserID           uint64  `ch:"user_id"`
	Email            string  `ch:"email"`
	FirstName        string  `ch:"first_name"`
	LastName         string  `ch:"last_name"`
	Country          string  `ch:"country"`
	ProsthesesCount  uint32  `ch:"prostheses_count"`
	UpdatedAt        time.Time `ch:"updated_at"`
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
	_ /*from*/, _ /*to*/ time.Time,
) ([]reportRow, error) {
	const q = `
		SELECT user_id, email, first_name, last_name, country,
		       prostheses_count, updated_at
		FROM crm_user_report FINAL
		WHERE user_id = ?
	`
	rows, err := c.conn.Query(ctx, q, userID)
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