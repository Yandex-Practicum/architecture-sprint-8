package auth

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"

	"reports-api/internal/config"
)

type ContextKey string

const SessionKey ContextKey = "session"

type SessionInfo struct {
	Active                 bool   `json:"active"`
	UserID                 string `json:"user_id"`
	SessionExpiresAtUnix   int64  `json:"session_expires_at_unix"`
	AccessTokenExpiresUnix int64  `json:"access_token_expires_unix"`
}

type Client struct {
	cfg    config.Config
	client *http.Client
}

func NewClient(cfg config.Config) *Client {
	return &Client{
		cfg: cfg,
		client: &http.Client{
			Timeout: cfg.RequestTimeout,
		},
	}
}

func (c *Client) ValidateSession(r *http.Request) (*SessionInfo, error) {
	cookie, err := r.Cookie(c.cfg.SessionCookieName)
	if err != nil {
		return nil, err
	}

	req, err := http.NewRequest(http.MethodGet, c.cfg.AuthServiceURL+"/api/session/validate", nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Cookie", cookie.String())

	resp, err := c.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, errors.New("invalid session")
	}

	var info SessionInfo
	if err := json.NewDecoder(resp.Body).Decode(&info); err != nil {
		return nil, err
	}

	if !info.Active || info.UserID == "" {
		return nil, errors.New("inactive session")
	}

	return &info, nil
}

type Middleware struct {
	Auth *Client
}

func (m *Middleware) RequireAuth(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		info, err := m.Auth.ValidateSession(r)
		if err != nil {
			http.Error(w, "unauthorized", http.StatusUnauthorized)
			return
		}

		ctx := context.WithValue(r.Context(), SessionKey, info)
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

func FromContext(ctx context.Context) (*SessionInfo, bool) {
	v := ctx.Value(SessionKey)
	if v == nil {
		return nil, false
	}
	info, ok := v.(*SessionInfo)
	return info, ok
}
