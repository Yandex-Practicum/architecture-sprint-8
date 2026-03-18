package httpx

import (
	"net/http"
	"time"
)

type CookieConfig struct {
	Name     string
	Domain   string
	Secure   bool
	SameSite http.SameSite
}

func SetSessionCookie(w http.ResponseWriter, cfg CookieConfig, sessionID string, expires time.Time) {
	http.SetCookie(w, &http.Cookie{
		Name:     cfg.Name,
		Value:    sessionID,
		Path:     "/",
		Domain:   cfg.Domain,
		HttpOnly: true,
		Secure:   cfg.Secure,
		SameSite: cfg.SameSite,
		Expires:  expires,
		MaxAge:   int(time.Until(expires).Seconds()),
	})
}

func ClearSessionCookie(w http.ResponseWriter, cfg CookieConfig) {
	http.SetCookie(w, &http.Cookie{
		Name:     cfg.Name,
		Value:    "",
		Path:     "/",
		Domain:   cfg.Domain,
		HttpOnly: true,
		Secure:   cfg.Secure,
		SameSite: cfg.SameSite,
		Expires:  time.Unix(0, 0),
		MaxAge:   -1,
	})
}
