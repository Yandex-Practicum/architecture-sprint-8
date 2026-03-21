package http

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"time"

	"reports-api/internal/auth"
	"reports-api/internal/repo"
	"reports-api/storage"
)

type Handlers struct {
	Reports repo.Repository
	Storage *storage.S3Storage
	CDNBase string
}

type ReportResponse struct {
	URL string `json:"url"`
}

func (h *Handlers) GetMyReport(w http.ResponseWriter, r *http.Request) {
	sess, ok := auth.FromContext(r.Context())
	if !ok {
		http.Error(w, "unauthorized", http.StatusUnauthorized)
		return
	}

	q := r.URL.Query()
	fromStr := q.Get("from")
	toStr := q.Get("to")

	var (
		from time.Time
		to   time.Time
		err  error
	)

	if fromStr == "" {
		from = time.Now().Add(-24 * time.Hour)
	} else {
		from, err = time.Parse("2006-01-02", fromStr)
		if err != nil {
			http.Error(w, "invalid from date", http.StatusBadRequest)
			return
		}
	}

	if toStr == "" {
		to = time.Now()
	} else {
		to, err = time.Parse("2006-01-02", toStr)
		if err != nil {
			http.Error(w, "invalid to date", http.StatusBadRequest)
			return
		}
	}

	key := buildObjectKey(sess.UserID, from, to)

	ctx := r.Context()

	exists, err := h.Storage.Exists(ctx, key)
	if err != nil {
		http.Error(w, "storage error", http.StatusInternalServerError)
		return
	}

	if !exists {
		report, err := h.Reports.GetUserReport(ctx, sess.UserID, from, to)
		if err != nil {
			http.Error(w, "failed to fetch report", http.StatusInternalServerError)
			return
		}
		md := buildMarkdownReport(report)

		if err := h.Storage.Put(ctx, key, []byte(md)); err != nil {
			http.Error(w, "failed to store report", http.StatusInternalServerError)
			return
		}
	}

	cdnURL := fmt.Sprintf("%s/reports/%s", strings.TrimRight(h.CDNBase, "/"), key[len("reports/"):])

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(ReportResponse{URL: cdnURL})
}

func buildObjectKey(userID string, from, to time.Time) string {
	return fmt.Sprintf(
		"reports/%s/usage_%s_%s.md",
		userID,
		from.Format("2006-01-02"),
		to.Format("2006-01-02"),
	)
}

func buildMarkdownReport(report *repo.UserReport) string {
	var buf bytes.Buffer

	periodFrom := report.PeriodFrom.Format("2006-01-02")
	periodTo := report.PeriodTo.Format("2006-01-02")

	fmt.Fprintf(&buf, "# Usage report for %s\n\n", report.FullName)
	fmt.Fprintf(&buf, "User ID: `%s`\n\n", report.UserID)
	fmt.Fprintf(&buf, "Period: %s — %s\n\n", periodFrom, periodTo)

	if len(report.DailyUsages) == 0 {
		buf.WriteString("No data for selected period.\n")
		return buf.String()
	}

	buf.WriteString("| Date | Serial | Duration, min | Avg load | Max load | Events |\n")
	buf.WriteString("| ---- | ------ | ------------- | -------- | -------- | ------ |\n")

	for _, row := range report.DailyUsages {
		date := row.Date.Format("2006-01-02")
		durationMin := float64(row.TotalDurationSec) / 60.0

		fmt.Fprintf(
			&buf,
			"| %s | %s | %.1f | %.2f | %.2f | %d |\n",
			date,
			row.SerialNumber,
			durationMin,
			row.AvgLoad,
			row.MaxLoad,
			row.EventsCount,
		)
	}

	return buf.String()
}
