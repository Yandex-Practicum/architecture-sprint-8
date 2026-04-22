package main

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"database/sql"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"
	_ "modernc.org/sqlite"
)

const (
	pendingPrefix = "pending:"
	sessionPrefix = "session:"
)

type pendingData struct {
	CodeVerifier string `json:"code_verifier"`
}

type tokenPayload struct {
	AccessToken      string `json:"access_token"`
	RefreshToken     string `json:"refresh_token"`
	ExpiresIn        int    `json:"expires_in"`
	RefreshExpiresIn int    `json:"refresh_expires_in"`
}

type sessionRecord struct {
	AccessToken  string `json:"access_token"`
	RefreshToken string `json:"refresh_token"`
	ExpiresAt    int64  `json:"expires_at"`
}

func openProfileDB(path string) (*sql.DB, error) {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return nil, err
	}
	db, err := sql.Open("sqlite", path+"?_pragma=busy_timeout(5000)")
	if err != nil {
		return nil, err
	}
	if _, err := db.Exec(`CREATE TABLE IF NOT EXISTS user_profiles (
		sub TEXT PRIMARY KEY,
		provider_hint TEXT,
		profile_json TEXT NOT NULL,
		updated_at TEXT NOT NULL
	)`); err != nil {
		_ = db.Close()
		return nil, err
	}
	return db, nil
}

func upsertProfile(db *sql.DB, sub, providerHint string, profile map[string]any) error {
	b, err := json.Marshal(profile)
	if err != nil {
		return err
	}
	_, err = db.Exec(
		`INSERT INTO user_profiles(sub, provider_hint, profile_json, updated_at) VALUES(?,?,?,?)
		 ON CONFLICT(sub) DO UPDATE SET provider_hint=excluded.provider_hint, profile_json=excluded.profile_json, updated_at=excluded.updated_at`,
		sub, providerHint, string(b), time.Now().UTC().Format(time.RFC3339),
	)
	return err
}

func main() {
	redisAddr := getenv("REDIS_ADDR", "localhost:6379")
	rdb := redis.NewClient(&redis.Options{Addr: redisAddr})
	ctx := context.Background()
	if err := rdb.Ping(ctx).Err(); err != nil {
		log.Fatalf("redis: %v", err)
	}

	dbPath := getenv("PROFILE_DB_PATH", "/data/profiles.db")
	pdb, err := openProfileDB(dbPath)
	if err != nil {
		log.Fatalf("profile db: %v", err)
	}
	defer pdb.Close()

	h := &handler{
		rdb:           rdb,
		profileDB:     pdb,
		keycloakURL:   strings.TrimRight(getenv("KEYCLOAK_URL", "http://localhost:8080"), "/"),
		realm:         getenv("KEYCLOAK_REALM", "reports-realm"),
		clientID:      getenv("KEYCLOAK_CLIENT_ID", "bionicpro-auth"),
		clientSecret:  getenv("KEYCLOAK_CLIENT_SECRET", ""),
		redirectURI:   getenv("OAUTH2_REDIRECT_URI", "http://localhost:8000/auth/callback"),
		frontendURL:   getenv("FRONTEND_URL", "http://localhost:3000/"),
		secureCookie:  getenv("SESSION_SECURE_COOKIES", "false") == "true",
		cookieName:    getenv("SESSION_COOKIE_NAME", "BIONIC_SESSION"),
		sessionMaxAge: 24 * time.Hour,
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/auth/login", h.handleLogin)
	mux.HandleFunc("/auth/callback", h.handleCallback)
	mux.HandleFunc("/auth/logout", h.handleLogout)
	mux.HandleFunc("/auth/me", h.withSessionRotation(h.handleMe, false))
	mux.HandleFunc("/reports", h.withSessionRotation(h.handleReports, true))

	addr := getenv("LISTEN_ADDR", ":8000")
	log.Printf("bionicpro-auth listening on %s", addr)
	log.Fatal(http.ListenAndServe(addr, withCORS(mux, getenv("CORS_ORIGIN", "http://localhost:3000"))))
}

func getenv(k, def string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return def
}

type handler struct {
	rdb            *redis.Client
	profileDB      *sql.DB
	keycloakURL    string
	realm          string
	clientID       string
	clientSecret   string
	redirectURI    string
	frontendURL    string
	secureCookie   bool
	cookieName     string
	sessionMaxAge  time.Duration
}

func (h *handler) tokenURL() string {
	return fmt.Sprintf("%s/realms/%s/protocol/openid-connect/token", h.keycloakURL, h.realm)
}

func (h *handler) authURL() string {
	return fmt.Sprintf("%s/realms/%s/protocol/openid-connect/auth", h.keycloakURL, h.realm)
}

func (h *handler) userinfoURL() string {
	return fmt.Sprintf("%s/realms/%s/protocol/openid-connect/userinfo", h.keycloakURL, h.realm)
}

func (h *handler) handleLogin(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "method", http.StatusMethodNotAllowed)
		return
	}
	state := randomURLString(32)
	verifier := randomPKCEVerifier()
	challenge := pkceChallengeS256(verifier)
	ctx := r.Context()
	pd, _ := json.Marshal(pendingData{CodeVerifier: verifier})
	if err := h.rdb.Set(ctx, pendingPrefix+state, pd, 10*time.Minute).Err(); err != nil {
		http.Error(w, "storage", http.StatusInternalServerError)
		return
	}
	q := url.Values{}
	q.Set("client_id", h.clientID)
	q.Set("redirect_uri", h.redirectURI)
	q.Set("response_type", "code")
	q.Set("scope", "openid profile email")
	q.Set("state", state)
	q.Set("code_challenge", challenge)
	q.Set("code_challenge_method", "S256")
	http.Redirect(w, r, h.authURL()+"?"+q.Encode(), http.StatusFound)
}

func (h *handler) handleCallback(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "method", http.StatusMethodNotAllowed)
		return
	}
	q := r.URL.Query()
	if errParam := q.Get("error"); errParam != "" {
		http.Error(w, errParam+": "+q.Get("error_description"), http.StatusBadRequest)
		return
	}
	state := q.Get("state")
	code := q.Get("code")
	if state == "" || code == "" {
		http.Error(w, "missing state or code", http.StatusBadRequest)
		return
	}
	ctx := r.Context()
	raw, err := h.rdb.Get(ctx, pendingPrefix+state).Bytes()
	if err != nil || len(raw) == 0 {
		http.Error(w, "invalid state", http.StatusBadRequest)
		return
	}
	_ = h.rdb.Del(ctx, pendingPrefix+state)
	var pd pendingData
	if err := json.Unmarshal(raw, &pd); err != nil || pd.CodeVerifier == "" {
		http.Error(w, "bad pending", http.StatusBadRequest)
		return
	}

	form := url.Values{}
	form.Set("grant_type", "authorization_code")
	form.Set("client_id", h.clientID)
	form.Set("client_secret", h.clientSecret)
	form.Set("redirect_uri", h.redirectURI)
	form.Set("code", code)
	form.Set("code_verifier", pd.CodeVerifier)

	resp, err := http.Post(h.tokenURL(), "application/x-www-form-urlencoded", strings.NewReader(form.Encode()))
	if err != nil {
		http.Error(w, "token request", http.StatusBadGateway)
		return
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != http.StatusOK {
		http.Error(w, "token: "+string(body), http.StatusUnauthorized)
		return
	}
	var tp tokenPayload
	if err := json.Unmarshal(body, &tp); err != nil || tp.AccessToken == "" {
		http.Error(w, "token parse", http.StatusInternalServerError)
		return
	}
	expiresAt := time.Now().Unix() + int64(tp.ExpiresIn)
	if tp.ExpiresIn <= 0 {
		expiresAt = time.Now().Add(90 * time.Second).Unix()
	}

	sid := uuid.NewString()
	sr := sessionRecord{
		AccessToken:  tp.AccessToken,
		RefreshToken: tp.RefreshToken,
		ExpiresAt:    expiresAt,
	}
	sb, _ := json.Marshal(sr)
	if err := h.rdb.Set(ctx, sessionPrefix+sid, sb, h.sessionMaxAge).Err(); err != nil {
		http.Error(w, "session", http.StatusInternalServerError)
		return
	}
	h.setSessionCookie(w, sid, h.sessionMaxAge)
	_ = h.syncUserProfile(tp.AccessToken)
	http.Redirect(w, r, h.frontendURL, http.StatusFound)
}

func (h *handler) syncUserProfile(accessToken string) error {
	req, err := http.NewRequest(http.MethodGet, h.userinfoURL(), nil)
	if err != nil {
		return err
	}
	req.Header.Set("Authorization", "Bearer "+accessToken)
	res, err := http.DefaultClient.Do(req)
	if err != nil {
		return err
	}
	defer res.Body.Close()
	if res.StatusCode != http.StatusOK {
		return fmt.Errorf("userinfo %d", res.StatusCode)
	}
	var claims map[string]any
	if err := json.NewDecoder(res.Body).Decode(&claims); err != nil {
		return err
	}
	sub, _ := claims["sub"].(string)
	if sub == "" {
		return errors.New("no sub")
	}
	prov := ""
	if v, ok := claims["identity_provider"].(string); ok {
		prov = v
	}
	return upsertProfile(h.profileDB, sub, prov, claims)
}

func (h *handler) handleLogout(w http.ResponseWriter, r *http.Request) {
	sid, err := h.readSessionCookie(r)
	if err == nil && sid != "" {
		_ = h.rdb.Del(r.Context(), sessionPrefix+sid).Err()
	}
	http.SetCookie(w, &http.Cookie{
		Name:     h.cookieName,
		Value:    "",
		Path:     "/",
		MaxAge:   -1,
		HttpOnly: true,
		Secure:   h.secureCookie,
		SameSite: http.SameSiteLaxMode,
	})
	http.Redirect(w, r, h.frontendURL, http.StatusFound)
}

func (h *handler) handleMe(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.Write([]byte(`{"ok":true}`))
}

func (h *handler) handleReports(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.Write([]byte(`{"report":"usage-summary","status":"ok","message":"Report placeholder (session authenticated)"}`))
}

func (h *handler) withSessionRotation(inner http.HandlerFunc, rotate bool) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		sid, err := h.readSessionCookie(r)
		if err != nil || sid == "" {
			http.Error(w, "unauthorized", http.StatusUnauthorized)
			return
		}
		ctx := r.Context()
		srPtr, err := h.loadSession(ctx, sid)
		if err != nil {
			http.Error(w, "unauthorized", http.StatusUnauthorized)
			return
		}
		sr := *srPtr
		if time.Now().Unix() >= sr.ExpiresAt-5 {
			if sr.RefreshToken == "" {
				http.Error(w, "session expired", http.StatusUnauthorized)
				return
			}
			nr, err := h.refreshTokens(sr.RefreshToken)
			if err != nil {
				http.Error(w, "refresh failed", http.StatusUnauthorized)
				return
			}
			sr = *nr
			sb, _ := json.Marshal(sr)
			_ = h.rdb.Set(ctx, sessionPrefix+sid, sb, h.sessionMaxAge).Err()
		}
		if rotate {
			newID := uuid.NewString()
			sb, _ := json.Marshal(sr)
			pipe := h.rdb.TxPipeline()
			pipe.Set(ctx, sessionPrefix+newID, sb, h.sessionMaxAge)
			pipe.Del(ctx, sessionPrefix+sid)
			if _, err := pipe.Exec(ctx); err != nil {
				http.Error(w, "rotation", http.StatusInternalServerError)
				return
			}
			h.setSessionCookie(w, newID, h.sessionMaxAge)
		}
		inner(w, r)
	}
}

func (h *handler) readSessionCookie(r *http.Request) (string, error) {
	c, err := r.Cookie(h.cookieName)
	if err != nil {
		return "", err
	}
	if c.Value == "" {
		return "", errors.New("empty")
	}
	return c.Value, nil
}

func (h *handler) setSessionCookie(w http.ResponseWriter, sid string, ttl time.Duration) {
	http.SetCookie(w, &http.Cookie{
		Name:     h.cookieName,
		Value:    sid,
		Path:     "/",
		MaxAge:   int(ttl.Seconds()),
		HttpOnly: true,
		Secure:   h.secureCookie,
		SameSite: http.SameSiteLaxMode,
	})
}

func (h *handler) loadSession(ctx context.Context, sid string) (*sessionRecord, error) {
	raw, err := h.rdb.Get(ctx, sessionPrefix+sid).Bytes()
	if err != nil || len(raw) == 0 {
		return nil, err
	}
	var sr sessionRecord
	if err := json.Unmarshal(raw, &sr); err != nil {
		return nil, err
	}
	return &sr, nil
}

func (h *handler) refreshTokens(refresh string) (*sessionRecord, error) {
	form := url.Values{}
	form.Set("grant_type", "refresh_token")
	form.Set("client_id", h.clientID)
	form.Set("client_secret", h.clientSecret)
	form.Set("refresh_token", refresh)
	resp, err := http.Post(h.tokenURL(), "application/x-www-form-urlencoded", strings.NewReader(form.Encode()))
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("%s", body)
	}
	var tp tokenPayload
	if err := json.Unmarshal(body, &tp); err != nil {
		return nil, err
	}
	expiresAt := time.Now().Unix() + int64(tp.ExpiresIn)
	if tp.ExpiresIn <= 0 {
		expiresAt = time.Now().Add(90 * time.Second).Unix()
	}
	return &sessionRecord{
		AccessToken:  tp.AccessToken,
		RefreshToken: firstNonEmpty(tp.RefreshToken, refresh),
		ExpiresAt:    expiresAt,
	}, nil
}

func firstNonEmpty(a, b string) string {
	if a != "" {
		return a
	}
	return b
}

func withCORS(next http.Handler, origin string) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", origin)
		w.Header().Set("Access-Control-Allow-Credentials", "true")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Cookie")
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}

func randomURLString(n int) string {
	b := make([]byte, n)
	if _, err := rand.Read(b); err != nil {
		panic(err)
	}
	s := base64.RawURLEncoding.EncodeToString(b)
	if len(s) < n {
		return s
	}
	return s[:n]
}

func randomPKCEVerifier() string {
	const charset = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._~"
	b := make([]byte, 64)
	if _, err := rand.Read(b); err != nil {
		panic(err)
	}
	for i := range b {
		b[i] = charset[int(b[i])%len(charset)]
	}
	return string(b)
}

func pkceChallengeS256(verifier string) string {
	sum := sha256.Sum256([]byte(verifier))
	return base64.RawURLEncoding.EncodeToString(sum[:])
}
