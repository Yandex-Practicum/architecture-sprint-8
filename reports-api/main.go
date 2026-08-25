package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/http"
	"net/url"
	"os"
	"time"
)

const (
	minReportDate  = "1970-01-01"
	frontendOrigin = "http://localhost:3000"
)

type server struct {
	mart *mart
	auth *authenticator
}

type reportResponse struct {
	UserID string  `json:"user_id"`
	From   *string `json:"from"`
	To     *string `json:"to"`

	ProcessedUpTo *string     `json:"processed_up_to"`
	Rows          []reportRow `json:"rows"`
}

func main() {
	m, err := openMart(env("CLICKHOUSE_ADDR", "localhost:9000"), env("CLICKHOUSE_DB", "reports"))
	if err != nil {
		log.Fatalf("clickhouse: %v", err)
	}

	auth, err := newAuthenticator(os.Getenv("KEYCLOAK_JWKS_URL"), os.Getenv("KEYCLOAK_ISSUER"))
	if err != nil {
		log.Fatalf("keycloak: %v", err)
	}

	s := &server{mart: m, auth: auth}

	mux := http.NewServeMux()
	mux.HandleFunc("GET /reports", s.handleReports)
	mux.HandleFunc("OPTIONS /reports", func(w http.ResponseWriter, r *http.Request) {
		allowFrontend(w)
		w.Header().Set("Access-Control-Allow-Methods", "GET, OPTIONS")
		w.WriteHeader(http.StatusNoContent)
	})

	addr := ":" + env("PORT", "8000")
	log.Printf("reports-api is listening on %s", addr)
	log.Fatal(http.ListenAndServe(addr, mux))
}

func (s *server) handleReports(w http.ResponseWriter, r *http.Request) {
	allowFrontend(w)

	userID, err := s.auth.authenticate(r)
	if err != nil {
		var denied authError
		if errors.As(err, &denied) {
			http.Error(w, denied.message, denied.status)
			return
		}
		http.Error(w, "authentication failed", http.StatusUnauthorized)
		return
	}

	from, to, err := parsePeriod(r.URL.Query())
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	processed, err := s.mart.processedUpTo(r.Context())
	if err != nil {
		log.Printf("clickhouse: %v", err)
		http.Error(w, "report storage is unavailable", http.StatusServiceUnavailable)
		return
	}

	report := reportResponse{UserID: userID, Rows: []reportRow{}}
	if processed == "" {
		writeJSON(w, report)
		return
	}
	report.ProcessedUpTo = &processed

	if to == "" || to > processed {
		to = processed
	}
	if from == "" {
		from = minReportDate
	}
	if from > to {
		writeJSON(w, report)
		return
	}

	rows, err := s.mart.reportRows(r.Context(), userID, from, to)
	if err != nil {
		log.Printf("clickhouse: %v", err)
		http.Error(w, "report storage is unavailable", http.StatusServiceUnavailable)
		return
	}
	report.From, report.To, report.Rows = &from, &to, rows
	writeJSON(w, report)
}

func parsePeriod(query url.Values) (from, to string, err error) {
	for _, param := range []struct {
		name  string
		value *string
	}{{"from", &from}, {"to", &to}} {
		raw := query.Get(param.name)
		if raw == "" {
			continue
		}
		if _, err := time.Parse(time.DateOnly, raw); err != nil {
			return "", "", fmt.Errorf("%s must be a date in YYYY-MM-DD format", param.name)
		}
		*param.value = raw
	}
	if from != "" && to != "" && from > to {
		return "", "", errors.New("from must not be later than to")
	}
	return from, to, nil
}

func writeJSON(w http.ResponseWriter, report reportResponse) {
	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(report); err != nil {
		log.Printf("write response: %v", err)
	}
}

func allowFrontend(w http.ResponseWriter) {
	w.Header().Set("Access-Control-Allow-Origin", frontendOrigin)
	w.Header().Set("Access-Control-Allow-Headers", "Authorization")
}

func env(name, fallback string) string {
	if value := os.Getenv(name); value != "" {
		return value
	}
	return fallback
}
