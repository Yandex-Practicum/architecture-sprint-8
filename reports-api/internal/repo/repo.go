package repo

import (
	"context"
	"time"

	ch "github.com/ClickHouse/clickhouse-go/v2"
)

type DailyUsage struct {
	Date             time.Time `json:"date"`
	ProsthesisID     string    `json:"prosthesis_id"`
	SerialNumber     string    `json:"serial_number"`
	TotalDurationSec uint64    `json:"total_duration_sec"`
	AvgLoad          float64   `json:"avg_load"`
	MaxLoad          float64   `json:"max_load"`
	EventsCount      uint32    `json:"events_count"`
}

type UserReport struct {
	UserID      string       `json:"user_id"`
	ExternalID  string       `json:"external_id"`
	FullName    string       `json:"full_name"`
	PeriodFrom  time.Time    `json:"period_from"`
	PeriodTo    time.Time    `json:"period_to"`
	DailyUsages []DailyUsage `json:"daily_usages"`
}

type Repository interface {
	GetUserReport(ctx context.Context, userID string, from, to time.Time) (*UserReport, error)
}

type clickhouseRepo struct {
	conn ch.Conn
}

func NewClickHouse(conn ch.Conn) Repository {
	return &clickhouseRepo{conn: conn}
}

func (r *clickhouseRepo) GetUserReport(ctx context.Context, userID string, from, to time.Time) (*UserReport, error) {
	rows, err := r.conn.Query(ctx, `
        SELECT
            user_id,
            external_id,
            full_name,
            event_date,
            prosthesis_id,
            serial_number,
            total_duration_sec,
            avg_load,
            max_load,
            events_count
        FROM reports.user_usage_daily
        WHERE user_id = @user_id
          AND event_date BETWEEN @from_date AND @to_date
        ORDER BY event_date, prosthesis_id
    `, ch.Named("user_id", userID),
		ch.Named("from_date", from),
		ch.Named("to_date", to),
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var (
		report      UserReport
		dailyUsages []DailyUsage
	)

	for rows.Next() {
		var (
			userIDVal     string
			externalID    string
			fullName      string
			eventDate     time.Time
			prosthesisID  string
			serialNumber  string
			totalDuration uint64
			avgLoad       float64
			maxLoad       float64
			eventsCount   uint32
		)
		if err := rows.Scan(
			&userIDVal,
			&externalID,
			&fullName,
			&eventDate,
			&prosthesisID,
			&serialNumber,
			&totalDuration,
			&avgLoad,
			&maxLoad,
			&eventsCount,
		); err != nil {
			return nil, err
		}
		dailyUsages = append(dailyUsages, DailyUsage{
			Date:             eventDate,
			ProsthesisID:     prosthesisID,
			SerialNumber:     serialNumber,
			TotalDurationSec: totalDuration,
			AvgLoad:          avgLoad,
			MaxLoad:          maxLoad,
			EventsCount:      eventsCount,
		})
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}

	report.UserID = userID
	report.PeriodFrom = from
	report.PeriodTo = to
	report.DailyUsages = dailyUsages
	return &report, nil
}
