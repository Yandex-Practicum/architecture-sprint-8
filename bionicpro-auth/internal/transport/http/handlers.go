package http

import (
	"crypto/rand"
	"encoding/base64"
	"net/http"
	"time"

	"bionicpro-auth/internal/httpx"
	"bionicpro-auth/internal/keycloak"
	"bionicpro-auth/internal/session"
)

type Handlers struct {
	Keycloak            *keycloak.Client
	Sessions            *session.Manager
	Cookies             httpx.CookieConfig
	KeycloakRedirect    string
	FrontendURL         string
	PKCEStateCookieName string
	PKCEStateTTL        time.Duration
}

func (h *Handlers) Register(mux *http.ServeMux, authMW *httpx.AuthMiddleware) {
	mux.HandleFunc("/healthz", h.Healthz)
	mux.HandleFunc("/auth/login", h.Login)
	mux.HandleFunc("/auth/callback", h.Callback)
	mux.HandleFunc("/auth/logout", h.Logout)
	mux.Handle("/api/session", authMW.RequireSession(http.HandlerFunc(h.Session)))
	mux.Handle("/api/session/validate", authMW.RequireSession(http.HandlerFunc(h.Validate)))
}

func (h *Handlers) Healthz(w http.ResponseWriter, _ *http.Request) {
	httpx.JSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func (h *Handlers) Login(w http.ResponseWriter, r *http.Request) {
	state := randomID(32)
	nonce := randomID(32)
	returnTo := normalizeReturnTo(h.FrontendURL, r.URL.Query().Get("return_to"))

	pair, err := keycloak.NewPKCEPair()
	if err != nil {
		httpx.JSON(w, http.StatusInternalServerError, map[string]string{"error": "pkce generation failed"})
		return
	}

	err = setPKCEStateCookie(w, h.PKCEStateCookieName, h.Cookies.Domain, h.Cookies.Secure, h.Cookies.SameSite, h.PKCEStateTTL, pkceState{
		State:        state,
		ReturnTo:     returnTo,
		CodeVerifier: pair.Verifier,
	})
	if err != nil {
		httpx.JSON(w, http.StatusInternalServerError, map[string]string{"error": "pkce state store failed"})
		return
	}

	http.Redirect(w, r, h.Keycloak.AuthURL(
		h.KeycloakRedirect,
		state,
		nonce,
		pair.Challenge,
		pair.Method,
	), http.StatusFound)
}

func (h *Handlers) Callback(w http.ResponseWriter, r *http.Request) {
	code := r.URL.Query().Get("code")
	state := r.URL.Query().Get("state")
	if code == "" || state == "" {
		httpx.JSON(w, http.StatusBadRequest, map[string]string{"error": "missing code or state"})
		return
	}

	st, err := readPKCEStateCookie(r, h.PKCEStateCookieName)
	if err != nil {
		httpx.JSON(w, http.StatusUnauthorized, map[string]string{"error": "missing pkce state"})
		return
	}

	if err := verifyState(st.State, state); err != nil {
		httpx.JSON(w, http.StatusUnauthorized, map[string]string{"error": "invalid state"})
		return
	}

	tokenResp, err := h.Keycloak.ExchangeCode(r.Context(), code, h.KeycloakRedirect, st.CodeVerifier)
	if err != nil {
		httpx.JSON(w, http.StatusUnauthorized, map[string]string{"error": "token exchange failed"})
		return
	}

	userID, err := keycloak.ExtractSubFromAccessToken(tokenResp.AccessToken)
	if err != nil {
		httpx.JSON(w, http.StatusUnauthorized, map[string]string{"error": "invalid access token"})
		return
	}

	sess, err := h.Sessions.New(
		userID,
		tokenResp.AccessToken,
		time.Now().Add(time.Duration(tokenResp.ExpiresIn)*time.Second),
		tokenResp.RefreshToken,
	)
	if err != nil {
		httpx.JSON(w, http.StatusInternalServerError, map[string]string{"error": "session create failed"})
		return
	}

	httpx.SetSessionCookie(w, h.Cookies, sess.ID, sess.ExpiresAt)
	clearPKCEStateCookie(w, h.PKCEStateCookieName, h.Cookies.Domain, h.Cookies.Secure, h.Cookies.SameSite)

	http.Redirect(w, r, st.ReturnTo, http.StatusFound)
}

func (h *Handlers) Logout(w http.ResponseWriter, r *http.Request) {
	cookie, err := r.Cookie(h.Cookies.Name)
	if err == nil {
		h.Sessions.Delete(cookie.Value)
	}
	httpx.ClearSessionCookie(w, h.Cookies)
	w.WriteHeader(http.StatusNoContent)
}

func (h *Handlers) Session(w http.ResponseWriter, r *http.Request) {
	httpx.JSON(w, http.StatusOK, map[string]any{
		"authenticated": true,
	})
}

func (h *Handlers) Validate(w http.ResponseWriter, r *http.Request) {
	sess := r.Context().Value(httpx.SessionContextKey).(*session.Session)

	httpx.JSON(w, http.StatusOK, map[string]any{
		"active":                    true,
		"user_id":                   sess.UserID,
		"session_expires_at_unix":   sess.ExpiresAt.Unix(),
		"access_token_expires_unix": sess.AccessTokenExpiresAt.Unix(),
	})
}

func randomID(n int) string {
	b := make([]byte, n)
	_, _ = rand.Read(b)
	return base64.RawURLEncoding.EncodeToString(b)
}
