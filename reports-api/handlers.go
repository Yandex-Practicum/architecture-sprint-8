package main

import (
	"context"
	"encoding/json"
	"net/http"
	"strconv"
	"time"
)

type handlers struct {
	cfg config
	ch  *clickhouseClient
}

func newHandlers(cfg config, ch *clickhouseClient) *handlers {
	return &handlers{cfg: cfg, ch: ch}
}

func (h *handlers) health(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
	defer cancel()

	if err := h.ch.ping(ctx); err != nil {
		jsonError(w, http.StatusServiceUnavailable, "clickhouse_unavailable", err.Error())
		return
	}
	jsonOK(w, http.StatusOK, map[string]any{"status": "ok"})
}

func (h *handlers) reports(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		jsonError(w, http.StatusMethodNotAllowed, "method_not_allowed", "")
		return
	}

	q := r.URL.Query()
	userIDStr := q.Get("user_id")
	if userIDStr == "" {
		jsonError(w, http.StatusBadRequest, "missing_user_id", "user_id query param required")
		return
	}
	userID, err := strconv.ParseUint(userIDStr, 10, 64)
	if err != nil {
		jsonError(w, http.StatusBadRequest, "bad_user_id", err.Error())
		return
	}

	from, err := parseDate(q.Get("from"), time.Now().AddDate(0, 0, -30))
	if err != nil {
		jsonError(w, http.StatusBadRequest, "bad_from", err.Error())
		return
	}
	to, err := parseDate(q.Get("to"), time.Now())
	if err != nil {
		jsonError(w, http.StatusBadRequest, "bad_to", err.Error())
		return
	}
	if to.Before(from) {
		jsonError(w, http.StatusBadRequest, "bad_range", "to before from")
		return
	}

	ctx, cancel := context.WithTimeout(r.Context(), h.cfg.QueryTimeout)
	defer cancel()

	rows, err := h.ch.userReport(ctx, userID, from, to)
	if err != nil {
		jsonError(w, http.StatusBadGateway, "clickhouse_error", err.Error())
		return
	}

	out := make([]map[string]any, 0, len(rows))
	for _, r := range rows {
		out = append(out, map[string]any{
			"user_id":               r.UserID,
			"user_email":            r.UserEmail,
			"user_first_name":       r.UserFirstName,
			"user_last_name":        r.UserLastName,
			"user_country":          r.UserCountry,
			"prosthesis_id":         r.ProsthesisID,
			"prosthesis_model":      r.ProsthesisModel,
			"prosthesis_serial":     r.ProsthesisSerial,
			"report_date":           r.ReportDate.Format("2006-01-02"),
			"sessions_count":        r.SessionsCount,
			"total_active_minutes":  r.TotalActiveMinutes,
			"avg_signal_strength":   r.AvgSignalStrength,
			"max_signal_strength":   r.MaxSignalStrength,
			"error_events_count":    r.ErrorEventsCount,
			"battery_avg_percent":   r.BatteryAvgPercent,
			"actuator_cycles_total": r.ActuatorCyclesTotal,
		})
	}

	jsonOK(w, http.StatusOK, map[string]any{
		"user_id": userID,
		"from":    from.Format("2006-01-02"),
		"to":      to.Format("2006-01-02"),
		"rows":    out,
	})
}

func parseDate(s string, def time.Time) (time.Time, error) {
	if s == "" {
		return def, nil
	}
	return time.Parse("2006-01-02", s)
}

func jsonOK(w http.ResponseWriter, status int, body any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(body)
}

func jsonError(w http.ResponseWriter, status int, code, msg string) {
	jsonOK(w, status, map[string]any{"error": code, "message": msg})
}