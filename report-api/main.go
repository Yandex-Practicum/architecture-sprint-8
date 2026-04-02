package main

import (
	"context"
	"database/sql"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	_ "github.com/ClickHouse/clickhouse-go/v2"
	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
)

// ─── Конфигурация ────────────────────────────────────────────────────────────

var (
	chHost     = getenv("CLICKHOUSE_HOST", "clickhouse")
	chPort     = getenv("CLICKHOUSE_PORT", "8123")
	s3Endpoint = getenv("S3_ENDPOINT", "minio:9000")
	s3Key      = getenv("S3_ACCESS_KEY", "minioadmin")
	s3Secret   = getenv("S3_SECRET_KEY", "minioadmin")
	s3Bucket   = getenv("S3_BUCKET", "reports")
	cdnURL     = getenv("CDN_URL", "http://localhost/cdn")
)

// ─── Helpers ─────────────────────────────────────────────────────────────────

func getenv(k, def string) string {
	v := os.Getenv(k)
	if v == "" {
		return def
	}
	return v
}

// Получение sub из JWT (точное поведение как в C#)
func getUserIDFromToken(r *http.Request) *string {
	auth := r.Header.Get("Authorization")
	if !strings.HasPrefix(auth, "Bearer ") {
		return nil
	}

	jwt := strings.TrimPrefix(auth, "Bearer ")
	parts := strings.Split(jwt, ".")
	if len(parts) < 2 {
		return nil
	}

	// base64url decode
	p := parts[1]
	padding := (4 - len(p)%4) % 4
	p += strings.Repeat("=", padding)
	p = strings.ReplaceAll(strings.ReplaceAll(p, "-", "+"), "_", "/")

	bytes, err := base64.StdEncoding.DecodeString(p)
	if err != nil {
		return nil
	}

	var claims map[string]any
	if err := json.Unmarshal(bytes, &claims); err != nil {
		return nil
	}

	if sub, ok := claims["sub"].(string); ok {
		return &sub
	}

	return nil
}

func makeS3() (*minio.Client, error) {
	return minio.New(s3Endpoint, &minio.Options{
		Creds:  credentials.NewStaticV4(s3Key, s3Secret, ""),
		Secure: false,
	})
}

func ensureBucketExists(ctx context.Context, client *minio.Client, bucket string) error {
	exists, err := client.BucketExists(ctx, bucket)
	if err != nil {
		return err
	}
	if !exists {
		return client.MakeBucket(ctx, bucket, minio.MakeBucketOptions{})
	}
	return nil
}

// ─── Основной код ────────────────────────────────────────────────────────────

func main() {
	r := chi.NewRouter()
	r.Use(middleware.Logger)

	// GET /reports?user_id=<optional>
	r.Get("/reports", handleReports)

	r.Get("/health", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]any{"status": "ok"})
	})

	log.Println("Server running on :8080")
	http.ListenAndServe(":8080", r)
}

// ─── Handler /reports ───────────────────────────────────────────────────────

func handleReports(w http.ResponseWriter, r *http.Request) {
	ctx := context.Background()

	// 1) JWT → sub
	tokenUser := getUserIDFromToken(r)
	if tokenUser == nil {
		http.Error(w, "Unauthorized", http.StatusUnauthorized)
		return
	}

	// 2) RBAC
	queryUser := r.URL.Query().Get("user_id")
	if queryUser != "" && queryUser != *tokenUser {
		http.Error(w, "Forbidden", http.StatusForbidden)
		return
	}

	reportUser := *tokenUser
	s3KeyObj := fmt.Sprintf("reports/%s/latest.json", reportUser)

	// 3) Проверяем S3 кеш
	s3, err := makeS3()
	if err != nil {
		log.Println(err)
		http.Error(w, "S3 init failed", 500)
		return
	}

	_, err = s3.StatObject(ctx, s3Bucket, s3KeyObj, minio.StatObjectOptions{})
	if err == nil {
		// кеш найден
		writeJSON(w, http.StatusOK, map[string]any{
			"cdn_url": fmt.Sprintf("%s/%s", cdnURL, s3KeyObj),
			"cached":  true,
		})
		return
	}

	// 4) Читаем ClickHouse
	connStr := fmt.Sprintf("http://default:clickhouse@%s:%s/bionicpro", chHost, chPort)
	db, err := sql.Open("clickhouse", connStr)
	if err != nil {
		http.Error(w, "ClickHouse connection failed", 500)
		return
	}
	defer db.Close()

	query := `
        SELECT
            user_id, username, email,
            prosthesis_id, model,
            total_movements,
            round(avg_response_ms, 2) AS avg_response_ms,
            round(min_response_ms, 2) AS min_response_ms,
            round(max_response_ms, 2) AS max_response_ms,
            last_activity,
            report_date
        FROM bionicpro.user_reports_summary
        WHERE user_id = ?
          AND report_date < today()
        ORDER BY report_date DESC
        LIMIT 30
    `

	rows, err := db.QueryContext(ctx, query, reportUser)
	if err != nil {
		log.Println(err)
		http.Error(w, "ClickHouse query failed", 500)
		return
	}
	defer rows.Close()

	results := []map[string]any{}
	cols, _ := rows.Columns()

	for rows.Next() {
		values := make([]any, len(cols))
		ptrs := make([]any, len(cols))
		for i := range values {
			ptrs[i] = &values[i]
		}
		if err := rows.Scan(ptrs...); err != nil {
			http.Error(w, "CH row scan failed", 500)
			return
		}

		row := map[string]any{}
		for i, c := range cols {
			row[c] = values[i]
		}
		results = append(results, row)
	}

	if len(results) == 0 {
		writeJSON(w, http.StatusNotFound, map[string]any{
			"error": "Данных пока нет. Дождитесь следующего запуска Airflow DAG.",
		})
		return
	}

	// 5) Сохраняем в S3
	report := map[string]any{
		"user_id":      reportUser,
		"generated_at": time.Now().UTC(),
		"records":      results,
	}

	jsonBytes, _ := json.Marshal(report)

	if err := ensureBucketExists(ctx, s3, s3Bucket); err != nil {
		log.Println("ensureBucket error:", err)
	}

	_, err = s3.PutObject(ctx, s3Bucket, s3KeyObj, io.NopCloser(strings.NewReader(string(jsonBytes))),
		int64(len(jsonBytes)),
		minio.PutObjectOptions{
			ContentType: "application/json",
		})
	if err != nil {
		log.Println("S3 write failed (non-critical):", err)
	}

	writeJSON(w, http.StatusOK, map[string]any{
		"cdn_url": fmt.Sprintf("%s/%s", cdnURL, s3KeyObj),
		"cached":  false,
		"report":  report,
	})
}

// ─── JSON helper ─────────────────────────────────────────────────────────────

func writeJSON(w http.ResponseWriter, status int, data any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}