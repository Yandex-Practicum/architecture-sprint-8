package app

import (
	"net/http"

	"bionicpro-auth/internal/config"
	enc "bionicpro-auth/internal/crypto"
	"bionicpro-auth/internal/httpx"
	"bionicpro-auth/internal/keycloak"
	"bionicpro-auth/internal/session"
	httptransport "bionicpro-auth/internal/transport/http"
)

type App struct {
	server *http.Server
}

func New(cfg config.Config) (*App, error) {
	cipher, err := enc.New(cfg.RefreshTokenEncKey())
	if err != nil {
		return nil, err
	}

	kc := keycloak.New(
		cfg.KeycloakBaseURL,
		cfg.KeycloakSrvBaseURL,
		cfg.KeycloakRealm,
		cfg.KeycloakClientID,
		cfg.KeycloakClientSecret,
		cfg.KeycloakHTTPTimeout,
	)

	store := session.NewStore()
	manager := session.NewManager(store, cipher, kc, cfg.SessionTTL, cfg.AccessTokenLeeway)

	cookieCfg := httpx.CookieConfig{
		Name:     cfg.SessionCookieName,
		Domain:   cfg.CookieDomain,
		Secure:   cfg.CookieSecure,
		SameSite: cfg.CookieSameSite(),
	}

	authMW := &httpx.AuthMiddleware{
		CookieName: cfg.SessionCookieName,
		Sessions:   manager,
		Cookies:    cookieCfg,
	}

	handlers := &httptransport.Handlers{
		Keycloak:            kc,
		Sessions:            manager,
		Cookies:             cookieCfg,
		KeycloakRedirect:    cfg.KeycloakRedirectURL,
		FrontendURL:         cfg.FrontendURL,
		PKCEStateCookieName: cfg.PKCEStateCookieName,
		PKCEStateTTL:        cfg.PKCEStateTTL,
	}

	mux := http.NewServeMux()
	handlers.Register(mux, authMW)

	handler := httpx.CORS(cfg.AllowedOrigins)(mux)

	server := &http.Server{
		Addr:    cfg.HTTPAddr,
		Handler: handler,
	}

	return &App{server: server}, nil
}

func (a *App) Run() error {
	return a.server.ListenAndServe()
}
