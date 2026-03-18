package http

import (
	"crypto/subtle"
	"encoding/base64"
	"encoding/json"
	"errors"
	"net/http"
	"net/url"
	"time"
)

type pkceState struct {
	State        string `json:"state"`
	ReturnTo     string `json:"return_to"`
	CodeVerifier string `json:"code_verifier"`
}

func setPKCEStateCookie(w http.ResponseWriter, name, domain string, secure bool, sameSite http.SameSite, ttl time.Duration, st pkceState) error {
	raw, err := json.Marshal(st)
	if err != nil {
		return err
	}

	http.SetCookie(w, &http.Cookie{
		Name:     name,
		Value:    base64.RawURLEncoding.EncodeToString(raw),
		Path:     "/",
		Domain:   domain,
		HttpOnly: true,
		Secure:   secure,
		SameSite: sameSite,
		MaxAge:   int(ttl.Seconds()),
	})
	return nil
}

func readPKCEStateCookie(r *http.Request, name string) (*pkceState, error) {
	c, err := r.Cookie(name)
	if err != nil {
		return nil, err
	}

	raw, err := base64.RawURLEncoding.DecodeString(c.Value)
	if err != nil {
		return nil, err
	}

	var st pkceState
	if err := json.Unmarshal(raw, &st); err != nil {
		return nil, err
	}
	return &st, nil
}

func clearPKCEStateCookie(w http.ResponseWriter, name, domain string, secure bool, sameSite http.SameSite) {
	http.SetCookie(w, &http.Cookie{
		Name:     name,
		Value:    "",
		Path:     "/",
		Domain:   domain,
		HttpOnly: true,
		Secure:   secure,
		SameSite: sameSite,
		Expires:  time.Unix(0, 0),
		MaxAge:   -1,
	})
}

func verifyState(expected, actual string) error {
	if subtle.ConstantTimeCompare([]byte(expected), []byte(actual)) != 1 {
		return errors.New("invalid state")
	}
	return nil
}

func normalizeReturnTo(fallback, incoming string) string {
	if incoming == "" {
		return fallback
	}

	parsed, err := url.Parse(incoming)
	if err != nil {
		return fallback
	}

	if !parsed.IsAbs() {
		return fallback
	}

	return incoming
}
