package main

import (
	"net/http"
	"time"
)

func setSessionCookie(w http.ResponseWriter, cfg *config, sessID string) {
	http.SetCookie(w, &http.Cookie{
		Name:     cfg.CookieName,
		Value:    sessID,
		Path:     "/",
		Domain:   cfg.CookieDomain,
		HttpOnly: true,
		Secure:   cfg.Env == "prod",
		SameSite: http.SameSiteLaxMode,
		MaxAge:   int(cfg.SessionTTL.Seconds()),
	})
}

func clearSessionCookie(w http.ResponseWriter, cfg *config) {
	http.SetCookie(w, &http.Cookie{
		Name:     cfg.CookieName,
		Value:    "",
		Path:     "/",
		Domain:   cfg.CookieDomain,
		HttpOnly: true,
		Secure:   cfg.Env == "prod",
		SameSite: http.SameSiteLaxMode,
		MaxAge:   -1,
		Expires:  time.Unix(0, 0),
	})
}

func readSessionCookie(r *http.Request, cfg *config) (string, bool) {
	c, err := r.Cookie(cfg.CookieName)
	if err != nil || c.Value == "" {
		return "", false
	}
	return c.Value, true
}