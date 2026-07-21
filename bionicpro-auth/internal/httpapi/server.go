// Package httpapi wires the auth BFF HTTP surface: the PKCE login flow, the
// session-cookie lifecycle, session rotation and an authenticated reverse
// proxy to the downstream reports API.
package httpapi

import (
	"context"
	"log"
	"net/http"
	"net/http/httputil"
	"net/url"
	"strings"
	"sync"
	"time"

	"github.com/bionicpro/bionicpro-auth/internal/config"
	"github.com/bionicpro/bionicpro-auth/internal/oidc"
	"github.com/bionicpro/bionicpro-auth/internal/session"
)

const loginCookie = "bionicpro_login" // short-lived cookie binding a login attempt to the browser

// pendingLogin remembers the PKCE verifier for an in-flight authorization.
type pendingLogin struct {
	verifier string
	expires  time.Time
}

// Server holds all dependencies shared across handlers.
type Server struct {
	cfg      config.Config
	kc       *oidc.Client
	sessions *session.Store

	mu      sync.Mutex
	pending map[string]pendingLogin // keyed by state

	proxy *httputil.ReverseProxy // optional downstream reports API
}

// New builds the Server and its route mux.
func New(cfg config.Config, kc *oidc.Client, store *session.Store) *Server {
	s := &Server{
		cfg:      cfg,
		kc:       kc,
		sessions: store,
		pending:  make(map[string]pendingLogin),
	}
	if cfg.DownstreamAPIURL != "" {
		if target, err := url.Parse(cfg.DownstreamAPIURL); err == nil {
			proxy := httputil.NewSingleHostReverseProxy(target)
			base := proxy.Director
			proxy.Director = func(r *http.Request) {
				// Strip the /api gateway prefix: /api/reports -> <downstream>/reports.
				r.URL.Path = strings.TrimPrefix(r.URL.Path, "/api")
				if r.URL.Path == "" {
					r.URL.Path = "/"
				}
				base(r)
			}
			s.proxy = proxy
		} else {
			log.Printf("invalid DOWNSTREAM_API_URL %q: %v", cfg.DownstreamAPIURL, err)
		}
	}
	return s
}

// Handler returns the fully-configured HTTP handler with CORS applied.
func (s *Server) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", s.handleHealth)
	mux.HandleFunc("GET /auth/login", s.handleLogin)
	mux.HandleFunc("GET /auth/callback", s.handleCallback)
	mux.HandleFunc("GET /auth/me", s.withSession(s.handleMe))
	mux.HandleFunc("POST /auth/logout", s.handleLogout)
	// Protected resource(s): every call is authenticated and rotates the session.
	mux.HandleFunc("GET /api/reports", s.withSession(s.handleReports))
	mux.HandleFunc("/api/", s.withSession(s.handleProxy))
	return s.cors(mux)
}

func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

// cors allows the SPA origin to send credentialed (cookie) requests.
func (s *Server) cors(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		origin := r.Header.Get("Origin")
		if origin == s.cfg.FrontendURL {
			w.Header().Set("Access-Control-Allow-Origin", origin)
			w.Header().Set("Access-Control-Allow-Credentials", "true")
			w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
			w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
			w.Header().Set("Access-Control-Expose-Headers", "X-Session-Id")
			w.Header().Set("Vary", "Origin")
		}
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}

// gcPending drops expired pending logins under the lock.
func (s *Server) gcPending(now time.Time) {
	for k, v := range s.pending {
		if now.After(v.expires) {
			delete(s.pending, k)
		}
	}
}

// backgroundCtx returns a short-lived context for server-to-server calls.
func backgroundCtx() (context.Context, context.CancelFunc) {
	return context.WithTimeout(context.Background(), 10*time.Second)
}
