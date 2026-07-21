// Package httpapi exposes the reports API: GET /reports returns the
// authenticated user's own prosthesis report from the OLAP mart.
package httpapi

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"regexp"
	"strings"
	"time"

	"github.com/bionicpro/reports-api/internal/auth"
	"github.com/bionicpro/reports-api/internal/reports"
	"github.com/bionicpro/reports-api/internal/storage"
)

var dateRe = regexp.MustCompile(`^\d{4}-\d{2}-\d{2}$`)

// Options configures the reports API server.
type Options struct {
	RequiredRole string
	Timeout      time.Duration

	// Store, when set, enables the S3 + CDN cache. When nil the handler returns
	// the report body directly (no caching).
	Store      storage.ObjectStore
	Bucket     string
	CDNBaseURL string
	URLSecret  string
}

// Server holds the API dependencies.
type Server struct {
	verifier *auth.Verifier
	builder  *reports.Builder
	opts     Options
}

// New builds the reports API server.
func New(verifier *auth.Verifier, builder *reports.Builder, opts Options) *Server {
	return &Server{verifier: verifier, builder: builder, opts: opts}
}

// Handler returns the HTTP router.
func (s *Server) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
	})
	mux.HandleFunc("GET /reports", s.handleReports)
	return mux
}

// reportLink is returned when the S3 + CDN cache is enabled.
type reportLink struct {
	ReportURL           string `json:"report_url"`
	Cached              bool   `json:"cached"`
	ObjectKey           string `json:"object_key"`
	LatestProcessedDate string `json:"latest_processed_date"`
}

func (s *Server) handleReports(w http.ResponseWriter, r *http.Request) {
	// 1) Authentication: a valid Keycloak access token is mandatory.
	claims, err := s.authenticate(r)
	if err != nil {
		writeError(w, http.StatusUnauthorized, "unauthorized")
		return
	}

	// 2) Authorization by role (only prosthesis pilots have reports).
	if s.opts.RequiredRole != "" && !claims.HasRole(s.opts.RequiredRole) {
		writeError(w, http.StatusForbidden, "insufficient role")
		return
	}

	// 3) Self-only access: a user may only read their own report. If a `user`
	// parameter is supplied it must match the authenticated identity.
	target := claims.PreferredUsername
	if requested := r.URL.Query().Get("user"); requested != "" && requested != target {
		writeError(w, http.StatusForbidden, "you may only access your own report")
		return
	}

	// 4) Optional reporting window.
	from := r.URL.Query().Get("from")
	to := r.URL.Query().Get("to")
	if (from != "" && !dateRe.MatchString(from)) || (to != "" && !dateRe.MatchString(to)) {
		writeError(w, http.StatusBadRequest, "from/to must be YYYY-MM-DD")
		return
	}

	ctx, cancel := context.WithTimeout(r.Context(), s.opts.Timeout)
	defer cancel()

	if s.opts.Store == nil {
		// No cache configured: return the report body directly.
		report, err := s.builder.Build(ctx, target, from, to)
		if err != nil {
			writeError(w, http.StatusBadGateway, "failed to build report")
			return
		}
		writeJSON(w, http.StatusOK, report)
		return
	}

	s.serveCached(ctx, w, target, from, to)
}

// serveCached implements the cache-aside flow. The object key is versioned by
// the ETL watermark, so a data update yields a new key (and thus a fresh CDN
// object) while previously generated reports are served straight from the CDN
// without ever touching the OLAP store.
func (s *Server) serveCached(ctx context.Context, w http.ResponseWriter, user, from, to string) {
	watermark, err := s.builder.Watermark(ctx) // cheap metadata query
	if err != nil {
		writeError(w, http.StatusBadGateway, "failed to read watermark")
		return
	}
	key := s.objectKey(user, from, to, watermark)
	link := reportLink{
		ReportURL:           s.opts.CDNBaseURL + "/" + s.opts.Bucket + "/" + key,
		ObjectKey:           key,
		LatestProcessedDate: watermark,
	}

	exists, err := s.opts.Store.Exists(ctx, key)
	if err != nil {
		writeError(w, http.StatusBadGateway, "object store error")
		return
	}
	if exists {
		// Cache hit: no OLAP query at all.
		link.Cached = true
		writeJSON(w, http.StatusOK, link)
		return
	}

	// Cache miss: build the report once, store it, then hand back the CDN link.
	report, err := s.builder.Build(ctx, user, from, to)
	if err != nil {
		writeError(w, http.StatusBadGateway, "failed to build report")
		return
	}
	body, err := json.Marshal(report)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "encode error")
		return
	}
	if err := s.opts.Store.Put(ctx, key, body, "application/json"); err != nil {
		writeError(w, http.StatusBadGateway, "failed to store report")
		return
	}
	writeJSON(w, http.StatusOK, link)
}

// objectKey builds a deterministic, versioned and non-enumerable object key:
//
//	<user>/<from>_<to>_<watermark>_<sig>.json
//
// It is stable for the same (user, period, data version) — enabling reuse — and
// carries an HMAC signature so keys cannot be trivially guessed for other users.
func (s *Server) objectKey(user, from, to, watermark string) string {
	norm := func(v string) string {
		if v == "" {
			return "any"
		}
		return v
	}
	mac := hmac.New(sha256.New, []byte(s.opts.URLSecret))
	fmt.Fprintf(mac, "%s|%s|%s|%s", user, from, to, watermark)
	sig := hex.EncodeToString(mac.Sum(nil))[:12]
	return fmt.Sprintf("%s/%s_%s_%s_%s.json", user, norm(from), norm(to), norm(watermark), sig)
}

// authenticate extracts and verifies the bearer token.
func (s *Server) authenticate(r *http.Request) (*auth.Claims, error) {
	h := r.Header.Get("Authorization")
	token := strings.TrimSpace(strings.TrimPrefix(h, "Bearer "))
	if token == "" || token == h {
		return nil, errMissingToken
	}
	return s.verifier.Verify(token)
}

var errMissingToken = &authError{"missing bearer token"}

type authError struct{ msg string }

func (e *authError) Error() string { return e.msg }

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func writeError(w http.ResponseWriter, status int, msg string) {
	writeJSON(w, status, map[string]string{"error": msg})
}
