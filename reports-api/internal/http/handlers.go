package http

import (
	"bytes"
	"fmt"
	"net/http"
	"time"

	"reports-api/internal/auth"
	"reports-api/internal/repo"
)

type Handlers struct {
	Reports repo.Repository
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

	report, err := h.Reports.GetUserReport(r.Context(), sess.UserID, from, to)
	if err != nil {
		http.Error(w, "failed to fetch report", http.StatusInternalServerError)
		return
	}
	md := buildMarkdownReport(report)

	filename := fmt.Sprintf("usage-report-%s-%s.md",
		from.Format("2006-01-02"),
		to.Format("2006-01-02"),
	)

	w.Header().Set("Content-Type", "text/markdown; charset=utf-8")
	w.Header().Set("Content-Disposition", fmt.Sprintf(`attachment; filename="%s"`, filename))
	w.Header().Set("Content-Length", fmt.Sprintf("%d", len(md)))

	http.ServeContent(w, r, filename, time.Now(), bytes.NewReader([]byte(md)))
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
