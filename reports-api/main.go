package main

import (
	"context"
	"errors"
	"log"
	"net/http"
	"os/signal"
	"syscall"
	"time"
)

func main() {
	cfg := loadConfig()

	ch, err := newClickhouseClient(cfg)
	if err != nil {
		log.Fatalf("clickhouse: %v", err)
	}
	defer ch.close()

	if err := waitForClickhouse(ch); err != nil {
		log.Fatalf("clickhouse not reachable: %v", err)
	}
	log.Println("clickhouse connected")

	h := newHandlers(cfg, ch)

	mux := http.NewServeMux()
	mux.HandleFunc("/health", h.health)
	mux.HandleFunc("/reports", h.reports)

	srv := &http.Server{
		Addr:              cfg.Listen,
		Handler:           withRequestLog(mux),
		ReadHeaderTimeout: 10 * time.Second,
	}

	sigCtx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	go func() {
		log.Printf("reports-api listening on %s (env=%s)", cfg.Listen, cfg.Env)
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Fatalf("http server: %v", err)
		}
	}()

	<-sigCtx.Done()
	log.Println("shutting down...")
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	_ = srv.Shutdown(shutdownCtx)
}