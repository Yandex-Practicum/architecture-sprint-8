package app

import (
	"context"
	"log"
	"net/http"
	"time"

	"github.com/ClickHouse/clickhouse-go/v2"

	"reports-api/internal/auth"
	"reports-api/internal/config"
	handlers "reports-api/internal/http"
	"reports-api/internal/repo"
)

type App struct {
	server *http.Server
}

func New(cfg config.Config) (*App, error) {
	chConn, err := clickhouse.Open(&clickhouse.Options{
		Addr: []string{cfg.ClickHouseAddr},
		Auth: clickhouse.Auth{
			Database: cfg.ClickHouseDatabase,
			Username: cfg.ClickHouseUser,
			Password: cfg.ClickHousePassword,
		},
		DialTimeout: 5 * time.Second,
		Compression: &clickhouse.Compression{
			Method: clickhouse.CompressionLZ4,
		},
	})
	if err != nil {
		return nil, err
	}

	if err := chConn.Ping(context.Background()); err != nil {
		log.Printf("clickhouse ping error: %v", err)
	}

	repo := repo.NewClickHouse(chConn)
	authClient := auth.NewClient(cfg)
	authMW := &auth.Middleware{Auth: authClient}

	handlers := &handlers.Handlers{
		Reports: repo,
	}

	mux := http.NewServeMux()
	mux.Handle("/reports/me", authMW.RequireAuth(http.HandlerFunc(handlers.GetMyReport)))

	server := &http.Server{
		Addr:    cfg.HTTPAddr,
		Handler: cors(cfg, mux),
	}

	return &App{server: server}, nil
}

func (a *App) Run() error {
	return a.server.ListenAndServe()
}

// простой CORS для фронта
func cors(cfg config.Config, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		origin := r.Header.Get("Origin")
		allowed := false
		for _, o := range cfg.AllowedOrigins {
			if o == origin {
				allowed = true
				break
			}
		}
		if allowed {
			w.Header().Set("Access-Control-Allow-Origin", origin)
			w.Header().Set("Vary", "Origin")
			w.Header().Set("Access-Control-Allow-Credentials", "true")
			w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Accept")
			w.Header().Set("Access-Control-Allow-Methods", "GET, OPTIONS")
		}
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}
