package main

import (
	"crypto/rand"
	"encoding/hex"
	"errors"
	"log"
	"os"
	"time"
)

type config struct {
	Env      string
	Listen   string
	FrontURL string
	APIURL   string

	KeycloakURL    string
	KeycloakPublic string
	KeycloakRealm  string
	ClientID       string
	ClientSecret   string
	AuthCallback   string

	SessionEncKey []byte
	SessionTTL    time.Duration
	CookieDomain  string
	CookieName    string
}

func loadConfig() (*config, error) {
	cfg := &config{
		Env:           getenv("APP_ENV", "dev"),
		Listen:        getenv("LISTEN", ":8443"),
		FrontURL:      getenv("FRONT_URL", "http://localhost:3000"),
		APIURL:        getenv("API_URL", "http://reports-api:8000"),
		KeycloakURL:   getenv("KEYCLOAK_URL", "http://keycloak:8080"),
		KeycloakPublic: getenv("KEYCLOAK_PUBLIC_URL", getenv("KEYCLOAK_URL", "http://keycloak:8080")),
		KeycloakRealm: getenv("KEYCLOAK_REALM", "reports-realm"),
		ClientID:      getenv("KEYCLOAK_CLIENT_ID", "reports-frontend"),
		ClientSecret:  getenv("KEYCLOAK_CLIENT_SECRET", ""),
		AuthCallback:  getenv("AUTH_CALLBACK_URL", "http://localhost:8443/auth/callback"),
		CookieName:    getenv("COOKIE_NAME", "bp_session"),
		CookieDomain:  getenv("COOKIE_DOMAIN", ""),
		SessionTTL:    30 * time.Minute,
	}

	keyHex := os.Getenv("SESSION_ENC_KEY")
	if keyHex != "" {
		raw, err := hex.DecodeString(keyHex)
		if err != nil || len(raw) != 32 {
			return nil, errors.New("SESSION_ENC_KEY must be 32 bytes hex-encoded (64 hex chars)")
		}
		cfg.SessionEncKey = raw
	} else {
		buf := make([]byte, 32)
		if _, err := rand.Read(buf); err != nil {
			return nil, err
		}
		cfg.SessionEncKey = buf
		log.Println("WARNING: SESSION_ENC_KEY not set — generated ephemeral key. Sessions will not survive restart.")
	}

	if cfg.ClientID == "" {
		return nil, errors.New("KEYCLOAK_CLIENT_ID is required")
	}
	return cfg, nil
}

func getenv(k, def string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return def
}