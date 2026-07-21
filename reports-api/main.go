// Command reports-api serves per-user prosthesis reports from the ClickHouse
// OLAP mart produced by the Airflow ETL. It validates Keycloak access tokens
// and enforces that a user can only read their own report.
package main

import (
	"context"
	"errors"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/bionicpro/reports-api/internal/auth"
	"github.com/bionicpro/reports-api/internal/clickhouse"
	"github.com/bionicpro/reports-api/internal/config"
	"github.com/bionicpro/reports-api/internal/httpapi"
	"github.com/bionicpro/reports-api/internal/reports"
	"github.com/bionicpro/reports-api/internal/storage"
)

func main() {
	cfg := config.Load()
	httpClient := &http.Client{Timeout: cfg.HTTPTimeout}

	verifier := auth.NewVerifier(cfg.JWKSURL, cfg.Issuer, httpClient)
	ch := clickhouse.New(cfg.ClickHouseURL, cfg.ClickHouseUser, cfg.ClickHousePassword, httpClient)
	builder := reports.NewBuilder(ch, cfg.ClickHouseDB, cfg.ClickHouseTable, cfg.ClickHouseUseFinal)

	opts := httpapi.Options{
		RequiredRole: cfg.RequiredRole,
		Timeout:      cfg.HTTPTimeout,
		Bucket:       cfg.S3Bucket,
		CDNBaseURL:   cfg.CDNBaseURL,
		URLSecret:    cfg.URLSecret,
	}
	if cfg.S3Endpoint != "" {
		store, err := storage.NewMinioStore(cfg.S3Endpoint, cfg.S3AccessKey, cfg.S3SecretKey, cfg.S3Bucket, cfg.S3UseSSL)
		if err != nil {
			log.Fatalf("init object store: %v", err)
		}
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		if err := store.EnsureBucket(ctx); err != nil {
			log.Printf("ensure bucket %q: %v", cfg.S3Bucket, err)
		}
		cancel()
		opts.Store = store
		log.Printf("report cache enabled (s3=%s bucket=%s cdn=%s)", cfg.S3Endpoint, cfg.S3Bucket, cfg.CDNBaseURL)
	}

	srv := httpapi.New(verifier, builder, opts)

	httpServer := &http.Server{
		Addr:              cfg.ListenAddr,
		Handler:           srv.Handler(),
		ReadHeaderTimeout: 5 * time.Second,
	}

	go func() {
		log.Printf("reports-api listening on %s (clickhouse=%s/%s.%s)", cfg.ListenAddr, cfg.ClickHouseURL, cfg.ClickHouseDB, cfg.ClickHouseTable)
		if err := httpServer.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Fatalf("server error: %v", err)
		}
	}()

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGINT, syscall.SIGTERM)
	<-stop

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	_ = httpServer.Shutdown(ctx)
	log.Println("reports-api stopped")
}
