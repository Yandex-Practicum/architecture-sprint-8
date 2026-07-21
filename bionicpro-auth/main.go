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

	"github.com/bionicpro/bionicpro-auth/internal/config"
	"github.com/bionicpro/bionicpro-auth/internal/httpapi"
	"github.com/bionicpro/bionicpro-auth/internal/oidc"
	"github.com/bionicpro/bionicpro-auth/internal/session"
)

func main() {
	cfg := config.Load()

	kc := oidc.New(
		cfg.KCExternalBase,
		cfg.KCInternalBase,
		cfg.Realm,
		cfg.ClientID,
		cfg.ClientSecret,
		cfg.RedirectURI,
	)
	store := session.NewStore(cfg.SessionTTL)
	srv := httpapi.New(cfg, kc, store)

	httpServer := &http.Server{
		Addr:              cfg.ListenAddr,
		Handler:           srv.Handler(),
		ReadHeaderTimeout: 5 * time.Second,
	}

	go func() {
		log.Printf("bionicpro-auth listening on %s (realm=%s, client=%s)", cfg.ListenAddr, cfg.Realm, cfg.ClientID)
		if err := httpServer.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Fatalf("server error: %v", err)
		}
	}()

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGINT, syscall.SIGTERM)
	<-stop

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := httpServer.Shutdown(ctx); err != nil {
		log.Printf("graceful shutdown failed: %v", err)
	}
	log.Println("bionicpro-auth stopped")
}
