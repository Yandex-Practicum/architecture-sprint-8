// Package config loads reports-api settings from environment variables.
package config

import (
	"os"
	"time"
)

// Config holds all runtime settings for the reports API.
type Config struct {
	ListenAddr string

	// Keycloak: the issuer is validated against the token's `iss` claim (the
	// browser-facing URL), while JWKS is fetched over the internal URL.
	Issuer  string
	JWKSURL string

	// ClickHouse (OLAP) over its HTTP interface.
	ClickHouseURL      string
	ClickHouseDB       string
	ClickHouseUser     string
	ClickHousePassword string
	ClickHouseTable    string
	ClickHouseUseFinal bool // append FINAL — true for *MergeTree mart, false for a VIEW

	// Realm role that is allowed to pull prosthesis reports.
	RequiredRole string

	// S3 (MinIO) object store for the report cache. If S3Endpoint is empty the
	// service returns the report body directly (no caching layer).
	S3Endpoint  string
	S3AccessKey string
	S3SecretKey string
	S3Bucket    string
	S3UseSSL    bool

	// CDN base URL handed to clients, and the secret that signs cache keys.
	CDNBaseURL string
	URLSecret  string

	HTTPTimeout time.Duration
}

// Load reads configuration from the environment with local-friendly defaults.
func Load() Config {
	return Config{
		ListenAddr:         env("LISTEN_ADDR", ":8081"),
		Issuer:             env("KC_ISSUER", "http://localhost:8080/realms/reports-realm"),
		JWKSURL:            env("KC_JWKS_URL", "http://localhost:8080/realms/reports-realm/protocol/openid-connect/certs"),
		ClickHouseURL:      env("CLICKHOUSE_URL", "http://localhost:8123"),
		ClickHouseDB:       env("CLICKHOUSE_DB", "reports"),
		ClickHouseUser:     env("CLICKHOUSE_USER", "default"),
		ClickHousePassword: env("CLICKHOUSE_PASSWORD", ""),
		ClickHouseTable:    env("CLICKHOUSE_TABLE", "user_report_mart"),
		ClickHouseUseFinal: envBool("CLICKHOUSE_USE_FINAL", true),
		RequiredRole:       env("REQUIRED_ROLE", "prothetic_user"),
		S3Endpoint:         env("S3_ENDPOINT", ""),
		S3AccessKey:        env("S3_ACCESS_KEY", "minioadmin"),
		S3SecretKey:        env("S3_SECRET_KEY", "minioadmin"),
		S3Bucket:           env("S3_BUCKET", "reports"),
		S3UseSSL:           envBool("S3_USE_SSL", false),
		CDNBaseURL:         env("CDN_BASE_URL", "http://localhost:8090"),
		URLSecret:          env("REPORT_URL_SECRET", "cdn-signing-secret"),
		HTTPTimeout:        10 * time.Second,
	}
}

func envBool(key string, def bool) bool {
	if v, ok := os.LookupEnv(key); ok && v != "" {
		return v == "1" || v == "true" || v == "TRUE" || v == "True"
	}
	return def
}

func env(key, def string) string {
	if v, ok := os.LookupEnv(key); ok && v != "" {
		return v
	}
	return def
}
