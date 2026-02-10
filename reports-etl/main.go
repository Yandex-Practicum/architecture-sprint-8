package main

import (
	"database/sql"
	"log"
	"os"
	"time"

	_ "github.com/lib/pq"
)

const defaultDBURL = "postgresql://olap_user:olap_password@localhost:5434/olap_db?sslmode=disable"

func main() {
	dbURL := os.Getenv("OLAP_DATABASE_URL")
	if dbURL == "" {
		dbURL = defaultDBURL
	}
	db, err := sql.Open("postgres", dbURL)
	if err != nil {
		log.Fatalf("open db: %v", err)
	}
	defer db.Close()
	if err := db.Ping(); err != nil {
		log.Fatalf("ping db: %v", err)
	}

	if err := extractCRMAndTelemetry(db); err != nil {
		log.Fatalf("extract: %v", err)
	}
	if err := buildDatamart(db); err != nil {
		log.Fatalf("build_datamart: %v", err)
	}
	log.Println("reports ETL completed")
}

// extractCRMAndTelemetry inserts stub data into staging tables (in prod: real CRM/telemetry sources).
func extractCRMAndTelemetry(db *sql.DB) error {
	_, err := db.Exec(`
		INSERT INTO staging_crm (user_id, email, full_name, prosthesis_id)
		VALUES
			('user1-id', 'user1@example.com', 'User One', 'prosthesis-1'),
			('user2-id', 'user2@example.com', 'User Two', 'prosthesis-2')
	`)
	if err != nil {
		return err
	}
	_, err = db.Exec(`
		INSERT INTO staging_telemetry (user_id, event_time, metric_name, value)
		VALUES
			('user1-id', NOW() - INTERVAL '1 day', 'usage_hours', 4.5),
			('user1-id', NOW() - INTERVAL '1 day', 'steps', 1200),
			('user2-id', NOW() - INTERVAL '1 day', 'usage_hours', 3.0)
	`)
	return err
}

// buildDatamart aggregates telemetry by user and upserts into datamart_reports for the closed period.
func buildDatamart(db *sql.DB) error {
	periodTo := time.Now().UTC().AddDate(0, 0, -1)
	periodFrom := periodTo.AddDate(0, 0, -6)
	pFrom := periodFrom.Format("2006-01-02")
	pTo := periodTo.Format("2006-01-02")

	_, err := db.Exec(`
		INSERT INTO datamart_reports (user_id, period_from, period_to, summary)
		SELECT
			t.user_id,
			$1::date,
			$2::date,
			jsonb_build_object(
				'usage_hours', COALESCE(SUM(CASE WHEN t.metric_name = 'usage_hours' THEN t.value END), 0),
				'steps', COALESCE(SUM(CASE WHEN t.metric_name = 'steps' THEN t.value END), 0),
				'events_count', COUNT(*)::float
			)
		FROM staging_telemetry t
		WHERE t.event_time::date >= $1 AND t.event_time::date <= $2
		GROUP BY t.user_id
		ON CONFLICT (user_id, period_from, period_to)
		DO UPDATE SET summary = EXCLUDED.summary, report_generated_at = NOW()
	`, pFrom, pTo, pFrom, pTo)
	return err
}
