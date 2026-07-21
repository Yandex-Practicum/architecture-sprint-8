package httpapi

import (
	"context"
	"encoding/json"
	"log"
	"net/http"
	"time"

	"github.com/bionicpro/bionicpro-auth/internal/oidc"
	"github.com/bionicpro/bionicpro-auth/internal/session"
)

type ctxKey string

const sessionCtxKey ctxKey = "session"

// handleLogin starts the Authorization Code + PKCE flow. The verifier is kept
// server-side (never sent to the browser); only the challenge is forwarded to
// Keycloak. A state value is bound to the browser through a short-lived cookie.
func (s *Server) handleLogin(w http.ResponseWriter, r *http.Request) {
	verifier, challenge, err := oidc.GeneratePKCE()
	if err != nil {
		http.Error(w, "internal error", http.StatusInternalServerError)
		return
	}
	state, err := oidc.RandomState()
	if err != nil {
		http.Error(w, "internal error", http.StatusInternalServerError)
		return
	}

	s.mu.Lock()
	s.gcPending(time.Now())
	s.pending[state] = pendingLogin{verifier: verifier, expires: time.Now().Add(5 * time.Minute)}
	s.mu.Unlock()

	http.SetCookie(w, &http.Cookie{
		Name:     loginCookie,
		Value:    state,
		Path:     "/",
		HttpOnly: true,
		Secure:   s.cfg.CookieSecure,
		SameSite: http.SameSiteLaxMode,
		MaxAge:   300,
	})
	http.Redirect(w, r, s.kc.AuthorizationURL(state, challenge), http.StatusFound)
}

// handleCallback finishes the PKCE flow: validates state, exchanges the code
// for tokens, creates a server-side session and hands the browser only an
// opaque session cookie.
func (s *Server) handleCallback(w http.ResponseWriter, r *http.Request) {
	code := r.URL.Query().Get("code")
	state := r.URL.Query().Get("state")
	if code == "" || state == "" {
		http.Error(w, "missing code or state", http.StatusBadRequest)
		return
	}

	// state must match both the browser-bound cookie and a server-side record.
	c, err := r.Cookie(loginCookie)
	if err != nil || c.Value != state {
		http.Error(w, "invalid state", http.StatusBadRequest)
		return
	}
	s.mu.Lock()
	pl, ok := s.pending[state]
	delete(s.pending, state)
	s.mu.Unlock()
	if !ok || time.Now().After(pl.expires) {
		http.Error(w, "login session expired", http.StatusBadRequest)
		return
	}
	clearCookie(w, loginCookie, s.cfg.CookieSecure, s.cfg.CookieDomain)

	ctx, cancel := backgroundCtx()
	defer cancel()
	tok, err := s.kc.ExchangeCode(ctx, code, pl.verifier)
	if err != nil {
		log.Printf("code exchange failed: %v", err)
		http.Error(w, "authentication failed", http.StatusBadGateway)
		return
	}

	sess := sessionFromTokens(tok)
	created, err := s.sessions.Create(sess)
	if err != nil {
		http.Error(w, "internal error", http.StatusInternalServerError)
		return
	}
	s.setSessionCookie(w, created.ID)
	http.Redirect(w, r, s.cfg.FrontendURL, http.StatusFound)
}

// handleMe returns the current user's identity derived from the access token.
// The withSession middleware has already validated + rotated the session.
func (s *Server) handleMe(w http.ResponseWriter, r *http.Request) {
	sess := sessionFrom(r)
	writeJSON(w, http.StatusOK, map[string]any{
		"authenticated": true,
		"username":      sess.Username,
		"email":         sess.Email,
		"roles":         sess.Roles,
	})
}

// handleReports is a stand-in protected resource for Assignment 1. When a real
// reports backend is configured (DOWNSTREAM_API_URL) it is proxied instead
// (see handleProxy); otherwise we return a demo payload proving the access
// token is valid and bound to this session.
func (s *Server) handleReports(w http.ResponseWriter, r *http.Request) {
	if s.proxy != nil {
		s.handleProxy(w, r)
		return
	}
	sess := sessionFrom(r)
	writeJSON(w, http.StatusOK, map[string]any{
		"user":        sess.Username,
		"roles":       sess.Roles,
		"generatedAt": time.Now().UTC().Format(time.RFC3339),
		"note":        "demo report — real data source is delivered in Assignment 2",
	})
}

// handleProxy forwards to the downstream reports API, injecting the (freshly
// refreshed) access token so the browser never sees it.
func (s *Server) handleProxy(w http.ResponseWriter, r *http.Request) {
	if s.proxy == nil {
		http.Error(w, "downstream API not configured", http.StatusNotImplemented)
		return
	}
	sess := sessionFrom(r)
	r.Header.Set("Authorization", "Bearer "+sess.AccessToken)
	s.proxy.ServeHTTP(w, r)
}

// handleLogout revokes the tokens at Keycloak and clears the session + cookie.
func (s *Server) handleLogout(w http.ResponseWriter, r *http.Request) {
	if c, err := r.Cookie(s.cfg.CookieName); err == nil {
		if sess, ok := s.sessions.Get(c.Value); ok {
			ctx, cancel := backgroundCtx()
			defer cancel()
			if err := s.kc.RevokeRefreshToken(ctx, sess.RefreshToken); err != nil {
				log.Printf("token revocation failed: %v", err)
			}
			s.sessions.Delete(c.Value)
		}
	}
	clearCookie(w, s.cfg.CookieName, s.cfg.CookieSecure, s.cfg.CookieDomain)
	writeJSON(w, http.StatusOK, map[string]string{"status": "logged_out"})
}

// withSession is the auth middleware. It validates the session cookie, refreshes
// the access token when needed and rotates the session id on every call to
// defend against session fixation. The rotated session is placed in the request
// context and the new id is returned to the frontend via cookie + header.
func (s *Server) withSession(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		c, err := r.Cookie(s.cfg.CookieName)
		if err != nil {
			http.Error(w, "unauthorized", http.StatusUnauthorized)
			return
		}
		sess, ok := s.sessions.Get(c.Value)
		if !ok {
			clearCookie(w, s.cfg.CookieName, s.cfg.CookieSecure, s.cfg.CookieDomain)
			http.Error(w, "unauthorized", http.StatusUnauthorized)
			return
		}

		// Refresh the access token if it is about to expire. The service goes to
		// Keycloak with the refresh token — the frontend is never involved.
		if time.Now().After(sess.AccessExpiry.Add(-s.cfg.AccessSkew)) {
			ctx, cancel := backgroundCtx()
			tok, err := s.kc.Refresh(ctx, sess.RefreshToken)
			cancel()
			if err != nil {
				log.Printf("refresh failed for session: %v", err)
				s.sessions.Delete(sess.ID)
				clearCookie(w, s.cfg.CookieName, s.cfg.CookieSecure, s.cfg.CookieDomain)
				http.Error(w, "unauthorized", http.StatusUnauthorized)
				return
			}
			applyTokens(&sess, tok)
		}

		// Session rotation: re-bind the tokens to a new session id.
		rotated, err := s.sessions.Replace(sess.ID, sess)
		if err != nil {
			http.Error(w, "unauthorized", http.StatusUnauthorized)
			return
		}
		s.setSessionCookie(w, rotated.ID)
		w.Header().Set("X-Session-Id", rotated.ID)

		ctx := context.WithValue(r.Context(), sessionCtxKey, rotated)
		next(w, r.WithContext(ctx))
	}
}

// --- helpers ---------------------------------------------------------------

func sessionFrom(r *http.Request) session.Session {
	sess, _ := r.Context().Value(sessionCtxKey).(session.Session)
	return sess
}

func sessionFromTokens(tok *oidc.TokenResponse) session.Session {
	var sess session.Session
	applyTokens(&sess, tok)
	return sess
}

// applyTokens copies a token response into a session, deriving expiry times and
// identity claims from the access token.
func applyTokens(sess *session.Session, tok *oidc.TokenResponse) {
	now := time.Now()
	sess.AccessToken = tok.AccessToken
	sess.RefreshToken = tok.RefreshToken
	sess.AccessExpiry = now.Add(time.Duration(tok.ExpiresIn) * time.Second)
	sess.RefreshExpiry = now.Add(time.Duration(tok.RefreshExpiresIn) * time.Second)
	if claims, err := oidc.ParseClaims(tok.AccessToken); err == nil {
		sess.Subject = claims.Subject
		sess.Username = claims.PreferredUsername
		sess.Email = claims.Email
		sess.Roles = claims.RealmAccess.Roles
	}
}

func (s *Server) setSessionCookie(w http.ResponseWriter, id string) {
	http.SetCookie(w, &http.Cookie{
		Name:     s.cfg.CookieName,
		Value:    id,
		Path:     "/",
		Domain:   s.cfg.CookieDomain,
		HttpOnly: true,
		Secure:   s.cfg.CookieSecure,
		SameSite: http.SameSiteLaxMode,
		MaxAge:   int(s.cfg.SessionTTL / time.Second),
	})
}

func clearCookie(w http.ResponseWriter, name string, secure bool, domain string) {
	http.SetCookie(w, &http.Cookie{
		Name:     name,
		Value:    "",
		Path:     "/",
		Domain:   domain,
		HttpOnly: true,
		Secure:   secure,
		SameSite: http.SameSiteLaxMode,
		MaxAge:   -1,
	})
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}
