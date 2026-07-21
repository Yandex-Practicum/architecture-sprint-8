// Package config loads bionicpro-auth settings from environment variables.
package config

import (
	"os"
	"strconv"
	"time"
)

// Config holds all runtime settings for the auth BFF.
type Config struct {
	ListenAddr string // address the HTTP server listens on

	// Keycloak has two base URLs because the browser and the service reach it
	// through different hostnames when running in Docker:
	//   ExternalBase — used to build redirect (authorize) URLs for the browser.
	//   InternalBase — used for server-to-server calls (token/refresh/logout).
	KCExternalBase string
	KCInternalBase string
	Realm          string
	ClientID       string
	ClientSecret   string
	RedirectURI    string // bionicpro-auth callback, must match the Keycloak client

	FrontendURL      string // SPA origin; used for CORS and post-login redirect
	PostLogoutURL    string // where Keycloak returns the browser after logout
	DownstreamAPIURL string // optional reports backend to proxy /api/* to

	CookieName   string
	CookieSecure bool
	CookieDomain string

	SessionTTL time.Duration // must be greater than the access token lifetime
	AccessSkew time.Duration // refresh the access token this long before it expires
}

// Load reads configuration from the environment, applying sane defaults so the
// service also runs locally with `go run` without Docker.
func Load() Config {
	return Config{
		ListenAddr:       env("LISTEN_ADDR", ":8000"),
		KCExternalBase:   env("KC_EXTERNAL_URL", "http://localhost:8080"),
		KCInternalBase:   env("KC_INTERNAL_URL", "http://localhost:8080"),
		Realm:            env("KC_REALM", "reports-realm"),
		ClientID:         env("KC_CLIENT_ID", "bionicpro-auth"),
		ClientSecret:     env("KC_CLIENT_SECRET", "bionicpro-auth-secret"),
		RedirectURI:      env("REDIRECT_URI", "http://localhost:8000/auth/callback"),
		FrontendURL:      env("FRONTEND_URL", "http://localhost:3000"),
		PostLogoutURL:    env("POST_LOGOUT_URL", "http://localhost:3000"),
		DownstreamAPIURL: env("DOWNSTREAM_API_URL", ""),
		CookieName:       env("COOKIE_NAME", "bionicpro_session"),
		CookieSecure:     envBool("COOKIE_SECURE", true),
		CookieDomain:     env("COOKIE_DOMAIN", ""),
		SessionTTL:       envDuration("SESSION_TTL", 30*time.Minute),
		AccessSkew:       envDuration("ACCESS_SKEW", 10*time.Second),
	}
}

func env(key, def string) string {
	if v, ok := os.LookupEnv(key); ok && v != "" {
		return v
	}
	return def
}

func envBool(key string, def bool) bool {
	if v, ok := os.LookupEnv(key); ok && v != "" {
		if b, err := strconv.ParseBool(v); err == nil {
			return b
		}
	}
	return def
}

func envDuration(key string, def time.Duration) time.Duration {
	if v, ok := os.LookupEnv(key); ok && v != "" {
		if d, err := time.ParseDuration(v); err == nil {
			return d
		}
	}
	return def
}
