package main

import (
	"database/sql"
	"encoding/json"
	"log"
	"net/http"
	"os"

	_ "github.com/lib/pq"
)

const defaultDBURL = "postgresql://olap_user:olap_password@localhost:5434/olap_db?sslmode=disable"

var db *sql.DB

func main() {
	dbURL := os.Getenv("OLAP_DATABASE_URL")
	if dbURL == "" {
		dbURL = defaultDBURL
	}
	var err error
	db, err = sql.Open("postgres", dbURL)
	if err != nil {
		log.Fatalf("open db: %v", err)
	}
	defer db.Close()
	if err := db.Ping(); err != nil {
		log.Fatalf("ping db: %v", err)
	}

	http.HandleFunc("/reports", handleReports)
	http.HandleFunc("/health", handleHealth)
	log.Fatal(http.ListenAndServe(":9000", nil))
}

// handleReports returns the latest report for the user identified by X-User-Id (set by bionicpro-auth).
func handleReports(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	userID := r.Header.Get("X-User-Id")
	if userID == "" {
		writeJSON(w, http.StatusUnauthorized, map[string]string{"error": "Unauthorized"})
		return
	}

	var periodFrom, periodTo, reportGeneratedAt string
	var summary []byte
	err := db.QueryRow(`
		SELECT period_from::text, period_to::text, report_generated_at::text, COALESCE(summary::text, '{}')
		FROM datamart_reports
		WHERE user_id = $1
		ORDER BY period_to DESC
		LIMIT 1
	`, userID).Scan(&periodFrom, &periodTo, &reportGeneratedAt, &summary)
	if err == sql.ErrNoRows {
		writeJSON(w, http.StatusNotFound, map[string]any{
			"error":   "report_not_ready",
			"message": "Данные за обработанный период ещё не готовы. Отчёт формируется по расписанию.",
		})
		return
	}
	if err != nil {
		log.Printf("query reports: %v", err)
		writeJSON(w, http.StatusInternalServerError, map[string]any{
			"error":   "internal_error",
			"message": "Ошибка при получении отчёта из OLAP. Проверьте логи reports-api и доступность olap_db.",
		})
		return
	}

	var summaryObj any
	if len(summary) > 0 {
		_ = json.Unmarshal(summary, &summaryObj)
	}
	if summaryObj == nil {
		summaryObj = map[string]any{}
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"user_id":             userID,
		"period_from":         periodFrom,
		"period_to":           periodTo,
		"report_generated_at": reportGeneratedAt,
		"summary":             summaryObj,
	})
}

func handleHealth(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func writeJSON(w http.ResponseWriter, code int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(v)
}
