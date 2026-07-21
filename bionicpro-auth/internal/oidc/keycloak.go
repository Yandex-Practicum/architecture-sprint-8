// Package oidc wraps the Keycloak OpenID Connect endpoints used by the BFF:
// the PKCE authorization-code exchange, the refresh-token grant and logout.
package oidc

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"
)

// Client talks to a single Keycloak realm.
type Client struct {
	ExternalBase string // browser-facing base URL (authorize endpoint)
	InternalBase string // server-to-server base URL (token/logout endpoints)
	Realm        string
	ClientID     string
	ClientSecret string
	RedirectURI  string
	HTTP         *http.Client
}

// New builds a Client with a bounded HTTP timeout.
func New(externalBase, internalBase, realm, clientID, clientSecret, redirectURI string) *Client {
	return &Client{
		ExternalBase: externalBase,
		InternalBase: internalBase,
		Realm:        realm,
		ClientID:     clientID,
		ClientSecret: clientSecret,
		RedirectURI:  redirectURI,
		HTTP:         &http.Client{Timeout: 10 * time.Second},
	}
}

func (c *Client) realmURL(base string) string {
	return strings.TrimRight(base, "/") + "/realms/" + c.Realm
}

// AuthorizationURL builds the browser redirect that starts the Authorization
// Code + PKCE flow. Only the code_challenge leaves the server; the verifier
// stays here and is sent later during the token exchange.
func (c *Client) AuthorizationURL(state, codeChallenge string) string {
	q := url.Values{}
	q.Set("client_id", c.ClientID)
	q.Set("response_type", "code")
	q.Set("scope", "openid profile email")
	q.Set("redirect_uri", c.RedirectURI)
	q.Set("state", state)
	q.Set("code_challenge", codeChallenge)
	q.Set("code_challenge_method", "S256")
	return c.realmURL(c.ExternalBase) + "/protocol/openid-connect/auth?" + q.Encode()
}

// LogoutURL builds the RP-initiated end-session URL for the browser.
func (c *Client) LogoutURL(postLogoutRedirect, idTokenHint string) string {
	q := url.Values{}
	q.Set("post_logout_redirect_uri", postLogoutRedirect)
	q.Set("client_id", c.ClientID)
	if idTokenHint != "" {
		q.Set("id_token_hint", idTokenHint)
	}
	return c.realmURL(c.ExternalBase) + "/protocol/openid-connect/logout?" + q.Encode()
}

// TokenResponse mirrors the fields we care about from Keycloak's token endpoint.
type TokenResponse struct {
	AccessToken      string `json:"access_token"`
	RefreshToken     string `json:"refresh_token"`
	IDToken          string `json:"id_token"`
	ExpiresIn        int    `json:"expires_in"`
	RefreshExpiresIn int    `json:"refresh_expires_in"`
	TokenType        string `json:"token_type"`
}

// ExchangeCode swaps an authorization code + PKCE verifier for tokens.
func (c *Client) ExchangeCode(ctx context.Context, code, codeVerifier string) (*TokenResponse, error) {
	form := url.Values{}
	form.Set("grant_type", "authorization_code")
	form.Set("code", code)
	form.Set("redirect_uri", c.RedirectURI)
	form.Set("code_verifier", codeVerifier)
	return c.tokenRequest(ctx, form)
}

// Refresh exchanges a refresh token for a fresh access/refresh token pair.
func (c *Client) Refresh(ctx context.Context, refreshToken string) (*TokenResponse, error) {
	form := url.Values{}
	form.Set("grant_type", "refresh_token")
	form.Set("refresh_token", refreshToken)
	return c.tokenRequest(ctx, form)
}

func (c *Client) tokenRequest(ctx context.Context, form url.Values) (*TokenResponse, error) {
	form.Set("client_id", c.ClientID)
	if c.ClientSecret != "" {
		form.Set("client_secret", c.ClientSecret)
	}
	endpoint := c.realmURL(c.InternalBase) + "/protocol/openid-connect/token"
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint, strings.NewReader(form.Encode()))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.Header.Set("Accept", "application/json")

	resp, err := c.HTTP.Do(req)
	if err != nil {
		return nil, fmt.Errorf("keycloak token request: %w", err)
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("keycloak token endpoint returned %s: %s", resp.Status, strings.TrimSpace(string(body)))
	}
	var tr TokenResponse
	if err := json.Unmarshal(body, &tr); err != nil {
		return nil, fmt.Errorf("decode token response: %w", err)
	}
	return &tr, nil
}

// RevokeRefreshToken invalidates a refresh token at the IdP (backchannel logout).
func (c *Client) RevokeRefreshToken(ctx context.Context, refreshToken string) error {
	form := url.Values{}
	form.Set("client_id", c.ClientID)
	if c.ClientSecret != "" {
		form.Set("client_secret", c.ClientSecret)
	}
	form.Set("refresh_token", refreshToken)
	endpoint := c.realmURL(c.InternalBase) + "/protocol/openid-connect/logout"
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint, strings.NewReader(form.Encode()))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	resp, err := c.HTTP.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	io.Copy(io.Discard, io.LimitReader(resp.Body, 1<<20))
	if resp.StatusCode >= 300 {
		return fmt.Errorf("keycloak logout returned %s", resp.Status)
	}
	return nil
}

// Claims holds the subset of access-token claims the BFF needs.
type Claims struct {
	Subject           string `json:"sub"`
	PreferredUsername string `json:"preferred_username"`
	Email             string `json:"email"`
	Expiry            int64  `json:"exp"`
	RealmAccess       struct {
		Roles []string `json:"roles"`
	} `json:"realm_access"`
}

// ParseClaims decodes (without signature verification) the JWT payload. The
// token is trusted because it was just retrieved directly from Keycloak's token
// endpoint over a server-to-server channel; we only need its claims for display
// and authorization, not to establish a trust boundary here.
func ParseClaims(token string) (*Claims, error) {
	parts := strings.Split(token, ".")
	if len(parts) < 2 {
		return nil, errors.New("malformed JWT")
	}
	payload, err := base64.RawURLEncoding.DecodeString(parts[1])
	if err != nil {
		// tolerate padded base64 just in case
		if payload, err = base64.StdEncoding.DecodeString(parts[1]); err != nil {
			return nil, fmt.Errorf("decode JWT payload: %w", err)
		}
	}
	var c Claims
	if err := json.Unmarshal(payload, &c); err != nil {
		return nil, fmt.Errorf("unmarshal claims: %w", err)
	}
	return &c, nil
}

// GeneratePKCE returns a random code_verifier and its S256 code_challenge.
func GeneratePKCE() (verifier, challenge string, err error) {
	b := make([]byte, 32)
	if _, err = rand.Read(b); err != nil {
		return "", "", err
	}
	verifier = base64.RawURLEncoding.EncodeToString(b)
	sum := sha256.Sum256([]byte(verifier))
	challenge = base64.RawURLEncoding.EncodeToString(sum[:])
	return verifier, challenge, nil
}

// RandomState returns an unguessable CSRF/state token.
func RandomState() (string, error) {
	b := make([]byte, 24)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	return base64.RawURLEncoding.EncodeToString(b), nil
}
