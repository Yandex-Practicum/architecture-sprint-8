package main

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"errors"
	"fmt"
	"log"
	"net/url"
	"strings"
	"sync/atomic"
	"time"

	"github.com/coreos/go-oidc/v3/oidc"
	"golang.org/x/oauth2"
)

type keycloakClient struct {
	cfg      *config
	authURL  atomic.Pointer[string]
	tokenURL atomic.Pointer[string]
	verifier atomic.Pointer[oidc.IDTokenVerifier]
}

func newKeycloakClient(ctx context.Context, cfg *config) *keycloakClient {
	kc := &keycloakClient{cfg: cfg}
	go kc.discoverLoop(ctx)
	return kc
}

func (k *keycloakClient) discoverLoop(ctx context.Context) {
	t := time.NewTicker(5 * time.Second)
	defer t.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-t.C:
			if k.authURL.Load() != nil {
				t.Reset(30 * time.Second)
				continue
			}
			if err := k.tryDiscover(ctx); err == nil {
				log.Printf("keycloak: discovery OK")
			}
		}
	}
}

func (k *keycloakClient) tryDiscover(ctx context.Context) error {
	issuer := strings.TrimRight(k.cfg.KeycloakURL, "/") + "/realms/" + k.cfg.KeycloakRealm
	dctx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()

	provider, err := oidc.NewProvider(dctx, issuer)
	if err != nil {
		return fmt.Errorf("oidc discovery: %w", err)
	}
	k.verifier.Store(provider.Verifier(&oidc.Config{ClientID: k.cfg.ClientID}))

	internal := strings.TrimRight(k.cfg.KeycloakURL, "/") + "/realms/" + k.cfg.KeycloakRealm + "/protocol/openid-connect"
	k.tokenURL.Store(strPtr(internal + "/token"))

	publicURL := strings.TrimRight(k.cfg.KeycloakPublic, "/") + "/realms/" + k.cfg.KeycloakRealm + "/protocol/openid-connect/auth"
	if k.cfg.KeycloakPublic == "" || k.cfg.KeycloakPublic == k.cfg.KeycloakURL {
		publicURL = provider.Endpoint().AuthURL
	}
	k.authURL.Store(strPtr(publicURL))
	return nil
}

func strPtr(s string) *string { return &s }

func (k *keycloakClient) ready() bool {
	return k.authURL.Load() != nil && k.tokenURL.Load() != nil
}

func (k *keycloakClient) authCodeURL(state, codeChallenge string) (string, error) {
	if !k.ready() {
		return "", errors.New("keycloak: not ready")
	}
	v := url.Values{}
	v.Set("response_type", "code")
	v.Set("client_id", k.cfg.ClientID)
	v.Set("redirect_uri", k.cfg.AuthCallback)
	v.Set("scope", "openid profile email")
	v.Set("state", state)
	v.Set("code_challenge", codeChallenge)
	v.Set("code_challenge_method", "S256")
	v.Set("nonce", state)
	return *k.authURL.Load() + "?" + v.Encode(), nil
}

func (k *keycloakClient) exchangeCode(ctx context.Context, code, codeVerifier string) (*tokenPair, error) {
	if !k.ready() {
		return nil, errors.New("keycloak: not ready")
	}
	cfg := &oauth2.Config{
		ClientID:     k.cfg.ClientID,
		ClientSecret: k.cfg.ClientSecret,
		RedirectURL:  k.cfg.AuthCallback,
		Endpoint: oauth2.Endpoint{
			AuthURL:  *k.authURL.Load(),
			TokenURL: *k.tokenURL.Load(),
		},
		Scopes: []string{"openid", "profile", "email"},
	}
	tok, err := cfg.Exchange(ctx, code, oauth2.SetAuthURLParam("code_verifier", codeVerifier))
	if err != nil {
		return nil, fmt.Errorf("oauth exchange: %w", err)
	}
	return k.fromOAuthToken(ctx, tok)
}

func (k *keycloakClient) refresh(ctx context.Context, refreshToken string) (*tokenPair, error) {
	if !k.ready() {
		return nil, errors.New("keycloak: not ready")
	}
	cfg := &oauth2.Config{
		ClientID:     k.cfg.ClientID,
		ClientSecret: k.cfg.ClientSecret,
		Endpoint: oauth2.Endpoint{
			AuthURL:  *k.authURL.Load(),
			TokenURL: *k.tokenURL.Load(),
		},
	}
	tok, err := cfg.TokenSource(ctx, &oauth2.Token{RefreshToken: refreshToken}).Token()
	if err != nil {
		return nil, fmt.Errorf("refresh: %w", err)
	}
	return k.fromOAuthToken(ctx, tok)
}

func (k *keycloakClient) fromOAuthToken(ctx context.Context, tok *oauth2.Token) (*tokenPair, error) {
	idTok, _ := tok.Extra("id_token").(string)
	claims := map[string]any{}
	if idTok != "" && k.verifier.Load() != nil {
		if v, err := k.verifier.Load().Verify(ctx, idTok); err == nil {
			_ = v.Claims(&claims)
		}
	}
	return &tokenPair{
		AccessToken:  tok.AccessToken,
		RefreshToken: tok.RefreshToken,
		IDToken:      idTok,
		Expiry:       tok.Expiry,
		Claims:       claims,
	}, nil
}

type tokenPair struct {
	AccessToken  string
	RefreshToken string
	IDToken      string
	Expiry       time.Time
	Claims       map[string]any
}

func newPKCE() (verifier, challenge string, err error) {
	buf := make([]byte, 32)
	if _, err = rand.Read(buf); err != nil {
		return "", "", err
	}
	verifier = base64.RawURLEncoding.EncodeToString(buf)
	h := sha256.Sum256([]byte(verifier))
	challenge = base64.RawURLEncoding.EncodeToString(h[:])
	return verifier, challenge, nil
}