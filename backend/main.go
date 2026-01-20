package main

import (
	"context"
	"log"
	"net/http"
	"time"

	"backend/config"
	"backend/handlers"
	"backend/middleware"
	"github.com/coreos/go-oidc/v3/oidc"
	"github.com/rs/cors"
)

func main() {
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("failed to load config: %v", err)
	}

	ctx := context.Background()
	provider, err := oidc.NewProvider(ctx, cfg.Issuer)
	if err != nil {
		log.Fatalf("failed to discover issuer: %v", err)
	}
	verifier := provider.Verifier(&oidc.Config{SkipClientIDCheck: true})

	mux := http.NewServeMux()
	mux.Handle(
		"/reports",
		middleware.AuthMiddleware(verifier, "prothetic_user")(http.HandlerFunc(handlers.ReportsHandler)),
	)

	c := cors.New(cors.Options{
		AllowedOrigins:   []string{"http://localhost:3000"},
		AllowedMethods:   []string{"GET", "POST", "OPTIONS"},
		AllowedHeaders:   []string{"Authorization", "Content-Type"},
		AllowCredentials: true,
	})
	handler := c.Handler(mux)

	srv := &http.Server{
		Addr:         cfg.ServerAddress,
		Handler:      handler,
		ReadTimeout:  5 * time.Second,
		WriteTimeout: 10 * time.Second,
		IdleTimeout:  120 * time.Second,
	}

	log.Printf("server listening on %s", cfg.ServerAddress)
	if err := srv.ListenAndServe(); err != nil {
		log.Fatalf("server failed: %v", err)
	}
}
