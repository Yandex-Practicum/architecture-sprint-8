package main

import (
	"context"
	"crypto/rand"
	"encoding/base64"
	"encoding/json"
	"net/http"
	"sync"
	"time"
)

type handlers struct {
	cfg   *config
	kx    *keycloakClient
	store *sessionStore

	pending   map[string]pendingPKCE
	pendingMu sync.Mutex
}

type pendingPKCE struct {
	Verifier  string
	Challenge string
	CreatedAt time.Time
}

func newHandlers(cfg *config, kx *keycloakClient, store *sessionStore) *handlers {
	return &handlers{
		cfg:     cfg,
		kx:      kx,
		store:   store,
		pending: make(map[string]pendingPKCE),
	}
}

func (h *handlers) health(w http.ResponseWriter, r *http.Request) {
	status := "ok"
	if !h.kx.ready() {
		status = "degraded"
	}
	jsonOK(w, 200, map[string]any{"status": status})
}

func (h *handlers) login(w http.ResponseWriter, r *http.Request) {
	if !h.kx.ready() {
		jsonError(w, 503, "keycloak_unavailable", "")
		return
	}
	state, err := randomURLSafe(24)
	if err != nil {
		jsonError(w, 500, "internal", err.Error())
		return
	}
	verifier, challenge, err := newPKCE()
	if err != nil {
		jsonError(w, 500, "internal", err.Error())
		return
	}

	h.pendingMu.Lock()
	h.pending[state] = pendingPKCE{Verifier: verifier, Challenge: challenge, CreatedAt: time.Now()}
	for k, p := range h.pending {
		if time.Since(p.CreatedAt) > 5*time.Minute {
			delete(h.pending, k)
		}
	}
	h.pendingMu.Unlock()

	authURL, err := h.kx.authCodeURL(state, challenge)
	if err != nil {
		jsonError(w, 503, "keycloak_unavailable", err.Error())
		return
	}
	http.Redirect(w, r, authURL, http.StatusFound)
}

func (h *handlers) callback(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	code := q.Get("code")
	state := q.Get("state")
	if errParam := q.Get("error"); errParam != "" {
		jsonError(w, 400, "oidc_error", errParam+": "+q.Get("error_description"))
		return
	}
	if code == "" || state == "" {
		jsonError(w, 400, "bad_request", "missing code or state")
		return
	}

	h.pendingMu.Lock()
	p, ok := h.pending[state]
	if ok {
		delete(h.pending, state)
	}
	h.pendingMu.Unlock()

	if !ok || time.Since(p.CreatedAt) > 5*time.Minute {
		jsonError(w, 400, "bad_state", "unknown or expired state")
		return
	}

	ctx, cancel := context.WithTimeout(r.Context(), 10*time.Second)
	defer cancel()

	tokens, err := h.kx.exchangeCode(ctx, code, p.Verifier)
	if err != nil {
		jsonError(w, 502, "oidc_exchange", err.Error())
		return
	}

	sessID, _, err := h.store.create(tokens)
	if err != nil {
		jsonError(w, 500, "session_create", err.Error())
		return
	}

	setSessionCookie(w, h.cfg, sessID)
	http.Redirect(w, r, h.cfg.FrontURL+"/", http.StatusFound)
}

func (h *handlers) requireSession(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		oldID, ok := readSessionCookie(r, h.cfg)
		if !ok {
			jsonError(w, 401, "no_session", "")
			return
		}
		sess, ok := h.store.get(oldID)
		if !ok || time.Now().After(sess.Expiry) {
			h.store.delete(oldID)
			clearSessionCookie(w, h.cfg)
			jsonError(w, 401, "session_expired", "")
			return
		}

		newID, _, err := h.store.rotate(oldID)
		if err != nil {
			jsonError(w, 500, "session_rotate", err.Error())
			return
		}
		setSessionCookie(w, h.cfg, newID)

		ctx := context.WithValue(r.Context(), sessionCtxKey{}, sess)
		next.ServeHTTP(w, r.WithContext(ctx))
	}
}

func (h *handlers) me(w http.ResponseWriter, r *http.Request) {
	sess := r.Context().Value(sessionCtxKey{}).(*session)
	jsonOK(w, 200, map[string]any{
		"user_id":  sess.UserID,
		"username": sess.Username,
	})
}

func (h *handlers) reports(w http.ResponseWriter, r *http.Request) {
	sessID, _ := readSessionCookie(r, h.cfg)
	ctx, cancel := context.WithTimeout(r.Context(), 15*time.Second)
	defer cancel()

	access, err := h.store.ensureFreshAccess(ctx, sessID, h.kx, 10*time.Second)
	if err != nil {
		h.store.delete(sessID)
		clearSessionCookie(w, h.cfg)
		jsonError(w, 401, "refresh_failed", err.Error())
		return
	}
	_ = access
	jsonOK(w, 200, map[string]any{
		"status":      "ready",
		"access_token": access,
		"hint":        "real /reports would proxy to API; omitted in this version",
	})
}

func (h *handlers) logout(w http.ResponseWriter, r *http.Request) {
	sessID, ok := readSessionCookie(r, h.cfg)
	if ok {
		h.store.delete(sessID)
	}
	clearSessionCookie(w, h.cfg)
	jsonOK(w, 200, map[string]any{"status": "logged_out"})
}

func randomURLSafe(n int) (string, error) {
	buf := make([]byte, n)
	if _, err := rand.Read(buf); err != nil {
		return "", err
	}
	return base64.RawURLEncoding.EncodeToString(buf), nil
}

type sessionCtxKey struct{}

func jsonOK(w http.ResponseWriter, status int, body any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(body)
}

func jsonError(w http.ResponseWriter, status int, code, msg string) {
	jsonOK(w, status, map[string]any{"error": code, "message": msg})
}