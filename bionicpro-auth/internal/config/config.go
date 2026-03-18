package config

import (
	"crypto/sha256"
	"errors"
	"net/http"
	"strings"
	"time"

	env "github.com/caarlos0/env/v11"
)

type Config struct {
	HTTPAddr       string   `env:"HTTP_ADDR" envDefault:":8082"`
	FrontendURL    string   `env:"FRONTEND_URL,required"`
	AllowedOrigins []string `env:"ALLOWED_ORIGINS" envSeparator:","`

	SessionCookieName string        `env:"SESSION_COOKIE_NAME" envDefault:"bionicpro_session"`
	SessionTTL        time.Duration `env:"SESSION_TTL" envDefault:"30m"`
	AccessTokenLeeway time.Duration `env:"ACCESS_TOKEN_LEEWAY" envDefault:"15s"`

	CookieDomain      string `env:"COOKIE_DOMAIN" envDefault:"localhost"`
	CookieSecure      bool   `env:"COOKIE_SECURE" envDefault:"true"`
	CookieSameSiteRaw string `env:"COOKIE_SAMESITE" envDefault:"None"`

	RefreshTokenSecret string `env:"REFRESH_TOKEN_ENC_SECRET,required"`

	KeycloakBaseURL      string        `env:"KEYCLOAK_BASE_URL,required"`
	KeycloakSrvBaseURL   string        `env:"KEYCLOAK_SRV_BASE_URL,required"`
	KeycloakRealm        string        `env:"KEYCLOAK_REALM,required"`
	KeycloakClientID     string        `env:"KEYCLOAK_CLIENT_ID,required"`
	KeycloakClientSecret string        `env:"KEYCLOAK_CLIENT_SECRET,required"`
	KeycloakRedirectURL  string        `env:"KEYCLOAK_REDIRECT_URL,required"`
	KeycloakHTTPTimeout  time.Duration `env:"KEYCLOAK_HTTP_TIMEOUT" envDefault:"10s"`

	PKCEStateCookieName string        `env:"PKCE_STATE_COOKIE_NAME" envDefault:"bionicpro_oauth_state"`
	PKCEStateTTL        time.Duration `env:"PKCE_STATE_TTL" envDefault:"5m"`
}

func Load() (Config, error) {
	var cfg Config
	if err := env.Parse(&cfg); err != nil {
		return Config{}, err
	}

	cfg.KeycloakBaseURL = strings.TrimRight(cfg.KeycloakBaseURL, "/")

	if len(cfg.AllowedOrigins) == 0 {
		cfg.AllowedOrigins = []string{cfg.FrontendURL}
	}

	if cfg.CookieSameSite() == http.SameSiteNoneMode && !cfg.CookieSecure {
		return Config{}, errors.New("COOKIE_SECURE must be true when COOKIE_SAMESITE=None")
	}

	return cfg, nil
}

func (c Config) CookieSameSite() http.SameSite {
	switch strings.ToLower(strings.TrimSpace(c.CookieSameSiteRaw)) {
	case "lax":
		return http.SameSiteLaxMode
	case "strict":
		return http.SameSiteStrictMode
	case "none":
		return http.SameSiteNoneMode
	default:
		return http.SameSiteLaxMode
	}
}

func (c Config) RefreshTokenEncKey() []byte {
	sum := sha256.Sum256([]byte(c.RefreshTokenSecret))
	return sum[:]
}
