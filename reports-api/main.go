package main

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/json"
	"log"
	"net/http"
	"os"
	"strings"
	"time"

	_ "github.com/ClickHouse/clickhouse-go/v2"
	_ "github.com/lib/pq"
	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
	"github.com/redis/go-redis/v9"
)

const (
	defaultDBURL   = "postgresql://olap_user:olap_password@localhost:5434/olap_db?sslmode=disable"
	reportCacheTTL = 5 * time.Minute
	s3KeyPrefix    = "reports/"
)

var (
	db            *sql.DB
	useClickHouse bool
	s3Client      *minio.Client
	redisClient   *redis.Client
	s3Bucket      string
	cdnBaseURL    string
	useS3         bool
)

func main() {
	var err error
	chDSN := os.Getenv("CLICKHOUSE_DSN")
	if chDSN != "" {
		useClickHouse = true
		db, err = sql.Open("clickhouse", chDSN)
		if err != nil {
			log.Fatalf("open ClickHouse: %v", err)
		}
		db.SetConnMaxLifetime(time.Minute * 3)
	} else {
		dbURL := os.Getenv("OLAP_DATABASE_URL")
		if dbURL == "" {
			dbURL = defaultDBURL
		}
		db, err = sql.Open("postgres", dbURL)
		if err != nil {
			log.Fatalf("open db: %v", err)
		}
	}
	defer db.Close()
	if err := db.Ping(); err != nil {
		log.Fatalf("ping db: %v", err)
	}

	s3Endpoint := os.Getenv("S3_ENDPOINT")
	s3AccessKey := os.Getenv("S3_ACCESS_KEY")
	s3SecretKey := os.Getenv("S3_SECRET_KEY")
	s3Bucket = os.Getenv("S3_BUCKET")
	if s3Bucket == "" {
		s3Bucket = "reports"
	}
	cdnBaseURL = strings.TrimSuffix(os.Getenv("CDN_BASE_URL"), "/")
	if cdnBaseURL == "" {
		cdnBaseURL = "http://localhost:8082"
	}
	if s3Endpoint != "" && s3AccessKey != "" && s3SecretKey != "" {
		s3Client, err = minio.New(s3Endpoint, &minio.Options{
			Creds:  credentials.NewStaticV4(s3AccessKey, s3SecretKey, ""),
			Secure: os.Getenv("S3_USE_SSL") == "true",
		})
		if err != nil {
			log.Fatalf("minio client: %v", err)
		}
		useS3 = true
		ensureBucket(context.Background())
	}

	redisAddr := os.Getenv("REDIS_ADDR")
	if redisAddr != "" {
		redisClient = redis.NewClient(&redis.Options{Addr: redisAddr})
		if err := redisClient.Ping(context.Background()).Err(); err != nil {
			log.Printf("redis ping failed (cache disabled): %v", err)
			redisClient = nil
		}
	}

	http.HandleFunc("/reports", handleReports)
	http.HandleFunc("/health", handleHealth)
	log.Fatal(http.ListenAndServe(":9000", nil))
}

func ensureBucket(ctx context.Context) {
	ok, err := s3Client.BucketExists(ctx, s3Bucket)
	if err != nil || !ok {
		if err = s3Client.MakeBucket(ctx, s3Bucket, minio.MakeBucketOptions{}); err != nil {
			log.Printf("make bucket %s: %v", s3Bucket, err)
		}
	}
}

// reportCacheKey returns Redis key for cached CDN URL for a user's latest report.
func reportCacheKey(userID string) string { return "report:url:" + userID }

// s3ObjectKey returns S3 object key for a report: reports/{userID}/{periodFrom}_{periodTo}.json
func s3ObjectKey(userID, periodFrom, periodTo string) string {
	from := strings.ReplaceAll(periodFrom, "-", "_")
	to := strings.ReplaceAll(periodTo, "-", "_")
	return s3KeyPrefix + userID + "/" + from + "_" + to + ".json"
}

// handleReports: 1) Redis cache → return URL; 2) OLAP latest row; 3) S3 exists → return URL + cache; 4) else upload to S3, return URL + cache.
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
	ctx := r.Context()

	if useS3 && redisClient != nil {
		if cached, err := redisClient.Get(ctx, reportCacheKey(userID)).Result(); err == nil {
			writeJSON(w, http.StatusOK, map[string]any{
				"url":         cached,
				"source":      "cdn_cache",
				"period_from": "",
				"period_to":   "",
			})
			return
		}
	}

	var periodFrom, periodTo, reportGeneratedAt string
	var summary []byte
	var err error
	if useClickHouse {
		var usageHours, steps float64
		var eventsCount uint64
		err = db.QueryRow(`
			SELECT toString(period_from), toString(period_to), toString(report_generated_at),
			       usage_hours, steps, events_count
			FROM datamart_reports FINAL
			WHERE user_id = ?
			ORDER BY period_to DESC
			LIMIT 1
		`, userID).Scan(&periodFrom, &periodTo, &reportGeneratedAt, &usageHours, &steps, &eventsCount)
		if err == nil {
			summary, _ = json.Marshal(map[string]any{
				"usage_hours":  usageHours,
				"steps":        steps,
				"events_count": float64(eventsCount),
			})
		}
	} else {
		err = db.QueryRow(`
			SELECT period_from::text, period_to::text, report_generated_at::text, COALESCE(summary::text, '{}')
			FROM datamart_reports
			WHERE user_id = $1
			ORDER BY period_to DESC
			LIMIT 1
		`, userID).Scan(&periodFrom, &periodTo, &reportGeneratedAt, &summary)
	}
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
			"message": "Ошибка при получении отчёта из OLAP.",
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

	if !useS3 || s3Client == nil {
		writeJSON(w, http.StatusOK, map[string]any{
			"user_id":             userID,
			"period_from":         periodFrom,
			"period_to":           periodTo,
			"report_generated_at": reportGeneratedAt,
			"summary":             summaryObj,
		})
		return
	}

	key := s3ObjectKey(userID, periodFrom, periodTo)
	cdnURL := cdnBaseURL + "/reports/" + userID + "/" + strings.ReplaceAll(periodFrom, "-", "_") + "_" + strings.ReplaceAll(periodTo, "-", "_") + ".json"

	reportBody := map[string]any{
		"user_id":             userID,
		"period_from":         periodFrom,
		"period_to":           periodTo,
		"report_generated_at": reportGeneratedAt,
		"summary":             summaryObj,
	}
	body, _ := json.Marshal(reportBody)
	_, err = s3Client.PutObject(ctx, s3Bucket, key, bytes.NewReader(body), int64(len(body)), minio.PutObjectOptions{ContentType: "application/json"})
	if err != nil {
		log.Printf("s3 put: %v", err)
		writeJSON(w, http.StatusOK, map[string]any{
			"user_id":             userID,
			"period_from":         periodFrom,
			"period_to":           periodTo,
			"report_generated_at": reportGeneratedAt,
			"summary":             summaryObj,
		})
		return
	}
	if redisClient != nil {
		_ = redisClient.Set(ctx, reportCacheKey(userID), cdnURL, reportCacheTTL).Err()
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"url":         cdnURL,
		"source":      "s3",
		"period_from": periodFrom,
		"period_to":   periodTo,
		"summary":     summaryObj,
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
