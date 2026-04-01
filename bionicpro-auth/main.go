package main

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"os"
	"strings"
	"sync"
	"time"
)

// ─────────────────────────────────────────────────────────────────────────────
// Конфигурация
// ─────────────────────────────────────────────────────────────────────────────

var (
	keycloakURL      = getEnv("KEYCLOAK_URL", "http://localhost:8080")
	keycloakTokenURL = getEnv("KEYCLOAK_TOKEN_URL", "http://localhost:8080")
	realm            = getEnv("KEYCLOAK_REALM", "reports-realm")
	clientId         = getEnv("KEYCLOAK_CLIENTID", "reports-frontend")
	clientSecret     = getEnv("KEYCLOAK_SECRET", "")
	redirectUri      = getEnv("KEYCLOAK_REDIRECTURI", "http://localhost:8001/auth/callback")
	frontendURL      = getEnv("FRONTEND_URL", "http://localhost:3000")
	reportApiURL     = getEnv("REPORTAPI_URL", "http://report-api:8080")

	accessTokenTTL = 120 * time.Second
	sessionTTL     = 3600 * time.Second
)

func getEnv(k, fallback string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return fallback
}

var tokenURL = fmt.Sprintf("%s/realms/%s/protocol/openid-connect/token", keycloakTokenURL, realm)
var authURL = fmt.Sprintf("%s/realms/%s/protocol/openid-connect/auth", keycloakURL, realm)

// ─────────────────────────────────────────────────────────────────────────────
// Модели и хранилища
// ─────────────────────────────────────────────────────────────────────────────

type SessionData struct {
	AccessToken   string
	RefreshToken  string
	TokenExpiry   time.Time
	SessionExpiry time.Time
	UserId        string
	Username      string
}

var (
	sessions  sync.Map // map[string]*SessionData
	pkceState sync.Map // map[state]code_verifier
)

// ─────────────────────────────────────────────────────────────────────────────
// Утилиты
// ─────────────────────────────────────────────────────────────────────────────

func base64URL(b []byte) string {
	return strings.TrimRight(base64.URLEncoding.EncodeToString(b), "=")
}

func randomBase64URL(n int) string {
	buf := make([]byte, n)
	_, _ = rand.Read(buf)
	return base64URL(buf)
}

func generateCodeVerifier() string {
	return randomBase64URL(32)
}

func generateCodeChallenge(verifier string) string {
	h := sha256.Sum256([]byte(verifier))
	return base64URL(h[:])
}

func parseJwtPayload(jwt string) (string, string) {
	parts := strings.Split(jwt, ".")
	if len(parts) < 2 {
		return "", ""
	}

	payload := parts[1]
	padding := len(payload) % 4
	if padding > 0 {
		payload += strings.Repeat("=", 4-padding)
	}

	raw, err := base64.URLEncoding.DecodeString(payload)
	if err != nil {
		return "", ""
	}

	var obj map[string]interface{}
	if err := json.Unmarshal(raw, &obj); err != nil {
		return "", ""
	}

	sub, _ := obj["sub"].(string)
	name, _ := obj["preferred_username"].(string)
	return sub, name
}

func newSessionID() string {
	return randomBase64URL(32)
}

// ─────────────────────────────────────────────────────────────────────────────
// Session helpers
// ─────────────────────────────────────────────────────────────────────────────

func tryGetValidSession(r *http.Request) (string, *SessionData, bool) {
	c, err := r.Cookie("session")
	if err != nil {
		return "", nil, false
	}
	id := c.Value

	val, ok := sessions.Load(id)
	if !ok {
		return "", nil, false
	}

	sess := val.(*SessionData)
	if time.Now().After(sess.SessionExpiry) {
		sessions.Delete(id)
		return "", nil, false
	}

	return id, sess, true
}

func rotateSession(old string, sess *SessionData, w http.ResponseWriter) string {
	sessions.Delete(old)
	newID := newSessionID()
	sessions.Store(newID, sess)

	http.SetCookie(w, &http.Cookie{
		Name:     "session",
		Value:    newID,
		Path:     "/",
		HttpOnly: true,
		SameSite: http.SameSiteLaxMode,
		MaxAge:   int(sessionTTL.Seconds()),
	})

	return newID
}

func refreshToken(sess *SessionData) bool {
	form := url.Values{}
	form.Set("grant_type", "refresh_token")
	form.Set("refresh_token", sess.RefreshToken)
	form.Set("client_id", clientId)
	if clientSecret != "" {
		form.Set("client_secret", clientSecret)
	}

	resp, err := http.PostForm(tokenURL, form)
	if err != nil || resp.StatusCode >= 300 {
		return false
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	var obj map[string]interface{}
	if err := json.Unmarshal(body, &obj); err != nil {
		return false
	}

	sess.AccessToken = obj["access_token"].(string)
	sess.TokenExpiry = time.Now().Add(accessTokenTTL)
	if rt, ok := obj["refresh_token"].(string); ok {
		sess.RefreshToken = rt
	}
	return true
}

// ─────────────────────────────────────────────────────────────────────────────
// HTTP Handlers
// ─────────────────────────────────────────────────────────────────────────────

func handleLogin(w http.ResponseWriter, r *http.Request) {
	state := newSessionID()
	verifier := generateCodeVerifier()
	challenge := generateCodeChallenge(verifier)

	pkceState.Store(state, verifier)

	params := url.Values{}
	params.Set("response_type", "code")
	params.Set("client_id", clientId)
	params.Set("redirect_uri", redirectUri)
	params.Set("scope", "openid profile email")
	params.Set("state", state)
	params.Set("code_challenge", challenge)
	params.Set("code_challenge_method", "S256")

	http.Redirect(w, r, authURL+"?"+params.Encode(), http.StatusFound)
}

func handleCallback(w http.ResponseWriter, r *http.Request) {
	code := r.URL.Query().Get("code")
	state := r.URL.Query().Get("state")

	val, ok := pkceState.Load(state)
	if !ok {
		http.Error(w, "Invalid state", http.StatusBadRequest)
		return
	}
	pkceState.Delete(state)
	verifier := val.(string)

	form := url.Values{}
	form.Set("grant_type", "authorization_code")
	form.Set("code", code)
	form.Set("redirect_uri", redirectUri)
	form.Set("client_id", clientId)
	form.Set("code_verifier", verifier)
	if clientSecret != "" {
		form.Set("client_secret", clientSecret)
	}

	resp, err := http.PostForm(tokenURL, form)
	log.Println(resp)
	log.Println(err)

	if err != nil || resp.StatusCode >= 300 {
		http.Error(w, "Token exchange failed", 500)
		return
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	var obj map[string]interface{}
	json.Unmarshal(body, &obj)

	access := obj["access_token"].(string)
	refresh := ""
	if v, ok := obj["refresh_token"].(string); ok {
		refresh = v
	}

	userId, username := parseJwtPayload(access)

	sid := newSessionID()
	sess := &SessionData{
		AccessToken:   access,
		RefreshToken:  refresh,
		TokenExpiry:   time.Now().Add(accessTokenTTL),
		SessionExpiry: time.Now().Add(sessionTTL),
		UserId:        userId,
		Username:      username,
	}
	sessions.Store(sid, sess)

	http.SetCookie(w, &http.Cookie{
		Name:     "session",
		Value:    sid,
		Path:     "/",
		HttpOnly: true,
		SameSite: http.SameSiteLaxMode,
		MaxAge:   int(sessionTTL.Seconds()),
	})

	http.Redirect(w, r, frontendURL, http.StatusFound)
}

func handleLogout(w http.ResponseWriter, r *http.Request) {
	id, _, ok := tryGetValidSession(r)
	if ok {
		sessions.Delete(id)
	}

	http.SetCookie(w, &http.Cookie{Name: "session", Value: "", MaxAge: -1, Path: "/"})
	http.Redirect(w, r, frontendURL, http.StatusFound)
}

func handleUserinfo(w http.ResponseWriter, r *http.Request) {
	old, sess, ok := tryGetValidSession(r)
	if !ok {
		w.WriteHeader(http.StatusUnauthorized)
		return
	}

	rotateSession(old, sess, w)

	json.NewEncoder(w).Encode(map[string]string{
		"userId":   sess.UserId,
		"username": sess.Username,
	})
}

func handleReports(w http.ResponseWriter, r *http.Request) {
	old, sess, ok := tryGetValidSession(r)
	if !ok {
		w.WriteHeader(http.StatusUnauthorized)
		return
	}

	if time.Now().After(sess.TokenExpiry) {
		if !refreshToken(sess) {
			w.WriteHeader(http.StatusUnauthorized)
			return
		}
	}

	rotateSession(old, sess, w)

	req, _ := http.NewRequestWithContext(context.Background(),
		"GET", fmt.Sprintf("%s/reports?user_id=%s", reportApiURL, sess.UserId), nil)
	req.Header.Set("Authorization", "Bearer "+sess.AccessToken)

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		w.WriteHeader(500)
		return
	}
	defer resp.Body.Close()

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(resp.StatusCode)
	io.Copy(w, resp.Body)
}

// ===== CORS =====
func cors(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {

		w.Header().Set("Access-Control-Allow-Origin", frontendURL)
		w.Header().Set("Access-Control-Allow-Credentials", "true")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}

		next.ServeHTTP(w, r)
	})
}

// ─────────────────────────────────────────────────────────────────────────────
// main
// ─────────────────────────────────────────────────────────────────────────────

func main() {
	mux := http.NewServeMux()

	mux.HandleFunc("/auth/login", handleLogin)
	mux.HandleFunc("/auth/callback", handleCallback)
	mux.HandleFunc("/auth/logout", handleLogout)
	mux.HandleFunc("/auth/userinfo", handleUserinfo)
	mux.HandleFunc("/api/reports", handleReports)
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		io.WriteString(w, `{"status":"ok"}`)
	})

	fmt.Println("BFF listening on :8001")
	log.Fatal(http.ListenAndServe(":8001", cors(mux)))
}
