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
	cfg, err := loadConfig()
	if err != nil {
		log.Fatalf("config: %v", err)
	}

	store := newSessionStore(cfg.SessionEncKey, cfg.SessionTTL)
	defer store.Close()

	kx := newKeycloakClient(context.Background(), cfg)
	h := newHandlers(cfg, kx, store)

	mux := http.NewServeMux()
	mux.HandleFunc("/health", h.health)
	mux.HandleFunc("/auth/login", h.login)
	mux.HandleFunc("/auth/callback", h.callback)
	mux.HandleFunc("/auth/logout", h.requireSession(h.logout))
	mux.HandleFunc("/auth/me", h.requireSession(h.me))
	mux.HandleFunc("/reports", h.requireSession(h.reports))

	handler := withCORS(cfg, withRequestLog(mux))

	srv := &http.Server{
		Addr:              cfg.Listen,
		Handler:           handler,
		ReadHeaderTimeout: 10 * time.Second,
	}

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	go func() {
		log.Printf("bionicpro-auth listening on %s (env=%s)", cfg.Listen, cfg.Env)
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Fatalf("http server: %v", err)
		}
	}()

	<-ctx.Done()
	log.Println("shutting down...")
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	_ = srv.Shutdown(shutdownCtx)
}