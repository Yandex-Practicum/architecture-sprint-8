package keycloak

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"
)

type Client struct {
	baseURL      string
	srvBaseURL   string
	realm        string
	clientID     string
	clientSecret string
	httpClient   *http.Client
}

func New(baseURL, srvBaseURL, realm, clientID, clientSecret string, timeout time.Duration) *Client {
	return &Client{
		baseURL:      strings.TrimRight(baseURL, "/"),
		srvBaseURL:   strings.TrimRight(srvBaseURL, "/"),
		realm:        realm,
		clientID:     clientID,
		clientSecret: clientSecret,
		httpClient:   &http.Client{Timeout: timeout},
	}
}

func (c *Client) AuthURL(redirectURI, state, nonce, codeChallenge, codeChallengeMethod string) string {
	q := url.Values{}
	q.Set("client_id", c.clientID)
	q.Set("response_type", "code")
	q.Set("scope", "openid profile email")
	q.Set("redirect_uri", redirectURI)
	q.Set("state", state)
	q.Set("nonce", nonce)
	q.Set("code_challenge", codeChallenge)
	q.Set("code_challenge_method", codeChallengeMethod)

	return c.baseURL + "/realms/" + c.realm + "/protocol/openid-connect/auth?" + q.Encode()
}

func (c *Client) ExchangeCode(ctx context.Context, code, redirectURI, codeVerifier string) (*TokenResponse, error) {
	form := url.Values{}
	form.Set("grant_type", "authorization_code")
	form.Set("client_id", c.clientID)
	form.Set("client_secret", c.clientSecret)
	form.Set("code", code)
	form.Set("redirect_uri", redirectURI)
	form.Set("code_verifier", codeVerifier)

	return c.postToken(ctx, form)
}

func (c *Client) Refresh(ctx context.Context, refreshToken string) (*TokenResponse, error) {
	form := url.Values{}
	form.Set("grant_type", "refresh_token")
	form.Set("client_id", c.clientID)
	form.Set("client_secret", c.clientSecret)
	form.Set("refresh_token", refreshToken)

	return c.postToken(ctx, form)
}

func (c *Client) postToken(ctx context.Context, form url.Values) (*TokenResponse, error) {
	endpoint := c.srvBaseURL + "/realms/" + c.realm + "/protocol/openid-connect/token"

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint, strings.NewReader(form.Encode()))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 300 {
		body, _ := io.ReadAll(resp.Body)
		return nil, errors.New(string(body))
	}

	var tr TokenResponse
	if err := json.NewDecoder(resp.Body).Decode(&tr); err != nil {
		return nil, err
	}
	return &tr, nil
}
