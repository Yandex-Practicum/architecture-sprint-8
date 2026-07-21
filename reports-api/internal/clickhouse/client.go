// Package clickhouse is a tiny client over ClickHouse's HTTP interface. It uses
// server-side parameter binding ({name:Type} + param_<name>) so user-supplied
// values can never be injected into SQL.
package clickhouse

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
)

// Client talks to ClickHouse over HTTP.
type Client struct {
	baseURL  string
	user     string
	password string
	http     *http.Client
}

// New builds a Client.
func New(baseURL, user, password string, httpClient *http.Client) *Client {
	return &Client{
		baseURL:  strings.TrimRight(baseURL, "/"),
		user:     user,
		password: password,
		http:     httpClient,
	}
}

// QueryJSON runs a read query and returns the raw ClickHouse `FORMAT JSON`
// response body. params are bound as {name:Type} placeholders.
func (c *Client) QueryJSON(ctx context.Context, query string, params map[string]string) ([]byte, error) {
	q := url.Values{}
	q.Set("default_format", "JSON")
	// Return 64-bit integers as JSON numbers (not strings) so they decode
	// directly into uint64/int64 fields.
	q.Set("output_format_json_quote_64bit_integers", "0")
	for k, v := range params {
		q.Set("param_"+k, v)
	}
	endpoint := c.baseURL + "/?" + q.Encode()

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint, strings.NewReader(query))
	if err != nil {
		return nil, err
	}
	if c.user != "" {
		req.Header.Set("X-ClickHouse-User", c.user)
	}
	if c.password != "" {
		req.Header.Set("X-ClickHouse-Key", c.password)
	}
	req.Header.Set("Content-Type", "text/plain")

	resp, err := c.http.Do(req)
	if err != nil {
		return nil, fmt.Errorf("clickhouse request: %w", err)
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(io.LimitReader(resp.Body, 8<<20))
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("clickhouse returned %s: %s", resp.Status, strings.TrimSpace(string(body)))
	}
	return body, nil
}
