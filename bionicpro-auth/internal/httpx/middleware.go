package httpx

import (
	"context"
	"net/http"

	"bionicpro-auth/internal/session"
)

type contextKey string

const SessionContextKey contextKey = "session"

type AuthMiddleware struct {
	CookieName string
	Sessions   *session.Manager
	Cookies    CookieConfig
}

func (m *AuthMiddleware) RequireSession(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		cookie, err := r.Cookie(m.CookieName)
		if err != nil {
			JSON(w, http.StatusUnauthorized, map[string]any{"error": "missing session"})
			return
		}

		sess, err := m.Sessions.ValidateAndRotate(r.Context(), cookie.Value)
		if err != nil {
			ClearSessionCookie(w, m.Cookies)
			JSON(w, http.StatusUnauthorized, map[string]any{"error": "invalid session"})
			return
		}

		SetSessionCookie(w, m.Cookies, sess.ID, sess.ExpiresAt)
		w.Header().Set("Cache-Control", `no-cache="Set-Cookie"`)
		w.Header().Set("Vary", "Cookie")
		w.Header().Set("X-Session-Rotated", "true")

		ctx := context.WithValue(r.Context(), SessionContextKey, sess)
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}
