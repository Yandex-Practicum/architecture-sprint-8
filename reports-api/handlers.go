package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"
	"time"
)

type handlers struct {
	cfg     config
	ch      *clickhouseClient
	storage *storage
}

func newHandlers(cfg config, ch *clickhouseClient, st *storage) *handlers {
	return &handlers{cfg: cfg, ch: ch, storage: st}
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

type reportPayload struct {
	UserID      uint64           `json:"user_id"`
	GeneratedAt time.Time        `json:"generated_at"`
	Rows        []map[string]any `json:"rows"`
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

	key := buildReportKey(userID)
	cdnURL := h.cfg.CDNBaseURL + "/" + key

	ctx, cancel := context.WithTimeout(r.Context(), h.cfg.QueryTimeout)
	defer cancel()

	hit, err := h.storage.has(ctx, key)
	if err != nil {
		logStorageWarn("head", key, err)
	} else if hit {
		jsonOK(w, http.StatusOK, map[string]any{
			"user_id": userID,
			"cache":   "hit",
			"key":     key,
			"cdn_url": cdnURL,
		})
		return
	}

	rows, err := h.ch.userReport(ctx, userID, time.Time{}, time.Time{})
	if err != nil {
		jsonError(w, http.StatusBadGateway, "clickhouse_error", err.Error())
		return
	}

	payload := reportPayload{
		UserID:      userID,
		GeneratedAt: time.Now().UTC(),
		Rows:        buildRows(rows),
	}
	body, err := json.MarshalIndent(payload, "", "  ")
	if err != nil {
		jsonError(w, http.StatusInternalServerError, "marshal_error", err.Error())
		return
	}

	if err := h.storage.put(ctx, key, body, "application/json"); err != nil {
		logStorageWarn("put", key, err)
		jsonError(w, http.StatusBadGateway, "storage_error", err.Error())
		return
	}

	jsonOK(w, http.StatusOK, map[string]any{
		"user_id": userID,
		"cache":   "miss",
		"key":     key,
		"cdn_url": cdnURL,
		"rows":    payload.Rows,
	})
}

func buildReportKey(userID uint64) string {
	return fmt.Sprintf("reports/crm/%d.json", userID)
}

func buildRows(rows []reportRow) []map[string]any {
	out := make([]map[string]any, 0, len(rows))
	for _, r := range rows {
		out = append(out, map[string]any{
			"user_id":           r.UserID,
			"email":             r.Email,
			"first_name":        r.FirstName,
			"last_name":         r.LastName,
			"country":           r.Country,
			"prostheses_count":  r.ProsthesesCount,
			"updated_at":        r.UpdatedAt.Format(time.RFC3339),
		})
	}
	return out
}

func logStorageWarn(op, key string, err error) {
	fmt.Printf("storage %s warning for %s: %v\n", op, key, err)
}

func parseDate(s string, def time.Time) (time.Time, error) {
	if s == "" {
		return def, nil
	}
	return time.Parse("2006-01-02", s)
}

func jsonOK(w http.ResponseWriter, status int, body any) {
	buf := &bytes.Buffer{}
	_ = json.NewEncoder(buf).Encode(body)
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	_, _ = w.Write(buf.Bytes())
}

func jsonError(w http.ResponseWriter, status int, code, msg string) {
	jsonOK(w, status, map[string]any{"error": code, "message": msg})
}