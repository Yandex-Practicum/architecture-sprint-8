package main

import (
	"os"
	"strconv"
	"time"
)

type config struct {
	Listen string
	Env    string

	ClickhouseHost     string
	ClickhousePort     int
	ClickhouseUser     string
	ClickhousePassword string
	ClickhouseDB       string
	QueryTimeout       time.Duration

	S3Endpoint  string
	S3AccessKey string
	S3SecretKey string
	S3Bucket    string
	S3UseSSL    bool
	S3Region    string

	CDNBaseURL string
}

func loadConfig() config {
	return config{
		Listen: getenv("LISTEN", ":8000"),
		Env:    getenv("APP_ENV", "dev"),

		ClickhouseHost:     getenv("CLICKHOUSE_HOST", "clickhouse"),
		ClickhousePort:     getenvInt("CLICKHOUSE_PORT", 9000),
		ClickhouseUser:     getenv("CLICKHOUSE_USER", "default"),
		ClickhousePassword: getenv("CLICKHOUSE_PASSWORD", ""),
		ClickhouseDB:       getenv("CLICKHOUSE_DB", "bionicpro_dm"),
		QueryTimeout:       10 * time.Second,

		S3Endpoint:  getenv("S3_ENDPOINT", "minio:9000"),
		S3AccessKey: getenv("S3_ACCESS_KEY", "minioadmin"),
		S3SecretKey: getenv("S3_SECRET_KEY", "minioadmin"),
		S3Bucket:    getenv("S3_BUCKET", "prosthesis-reports"),
		S3UseSSL:    getenv("S3_USE_SSL", "false") == "true",
		S3Region:    getenv("S3_REGION", "us-east-1"),

		CDNBaseURL: getenv("CDN_BASE_URL", "http://localhost:8081"),
	}
}

func getenv(k, def string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return def
}

func getenvInt(k string, def int) int {
	if v := os.Getenv(k); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			return n
		}
	}
	return def
}