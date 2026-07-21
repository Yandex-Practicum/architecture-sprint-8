// Package auth validates Keycloak-issued RS256 access tokens against the
// realm's JWKS, using only the Go standard library (no JWT dependency).
package auth

import (
	"crypto"
	"crypto/rsa"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math/big"
	"net/http"
	"strings"
	"sync"
	"time"
)

// Claims is the subset of access-token claims the reports API needs.
type Claims struct {
	Subject           string `json:"sub"`
	PreferredUsername string `json:"preferred_username"`
	Issuer            string `json:"iss"`
	Expiry            int64  `json:"exp"`
	AuthorizedParty   string `json:"azp"`
	RealmAccess       struct {
		Roles []string `json:"roles"`
	} `json:"realm_access"`
}

// HasRole reports whether the token carries the given realm role.
func (c *Claims) HasRole(role string) bool {
	for _, r := range c.RealmAccess.Roles {
		if r == role {
			return true
		}
	}
	return false
}

// Verifier verifies JWTs against a cached JWKS.
type Verifier struct {
	jwksURL string
	issuer  string
	http    *http.Client

	mu      sync.RWMutex
	keys    map[string]*rsa.PublicKey
	fetched time.Time
}

// NewVerifier builds a Verifier. JWKS is loaded lazily on first use and
// refreshed when an unknown key id appears (Keycloak key rotation).
func NewVerifier(jwksURL, issuer string, httpClient *http.Client) *Verifier {
	return &Verifier{
		jwksURL: jwksURL,
		issuer:  issuer,
		http:    httpClient,
		keys:    make(map[string]*rsa.PublicKey),
	}
}

type jwks struct {
	Keys []struct {
		Kid string `json:"kid"`
		Kty string `json:"kty"`
		N   string `json:"n"`
		E   string `json:"e"`
	} `json:"keys"`
}

func (v *Verifier) refreshKeys() error {
	req, err := http.NewRequest(http.MethodGet, v.jwksURL, nil)
	if err != nil {
		return err
	}
	resp, err := v.http.Do(req)
	if err != nil {
		return fmt.Errorf("fetch JWKS: %w", err)
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("JWKS endpoint returned %s", resp.Status)
	}
	var set jwks
	if err := json.Unmarshal(body, &set); err != nil {
		return fmt.Errorf("decode JWKS: %w", err)
	}
	keys := make(map[string]*rsa.PublicKey)
	for _, k := range set.Keys {
		if k.Kty != "RSA" {
			continue
		}
		pub, err := rsaPublicKey(k.N, k.E)
		if err != nil {
			continue
		}
		keys[k.Kid] = pub
	}
	v.mu.Lock()
	v.keys = keys
	v.fetched = time.Now()
	v.mu.Unlock()
	return nil
}

func (v *Verifier) keyFor(kid string) (*rsa.PublicKey, error) {
	v.mu.RLock()
	pub, ok := v.keys[kid]
	v.mu.RUnlock()
	if ok {
		return pub, nil
	}
	// Unknown kid: refresh once (throttled) and retry.
	v.mu.RLock()
	stale := time.Since(v.fetched) > time.Minute
	empty := len(v.keys) == 0
	v.mu.RUnlock()
	if stale || empty {
		if err := v.refreshKeys(); err != nil {
			return nil, err
		}
	}
	v.mu.RLock()
	pub, ok = v.keys[kid]
	v.mu.RUnlock()
	if !ok {
		return nil, fmt.Errorf("no JWKS key for kid %q", kid)
	}
	return pub, nil
}

// Verify checks the signature, algorithm, issuer and expiry of a bearer token
// and returns its claims.
func (v *Verifier) Verify(token string) (*Claims, error) {
	parts := strings.Split(token, ".")
	if len(parts) != 3 {
		return nil, errors.New("malformed JWT")
	}

	var header struct {
		Alg string `json:"alg"`
		Kid string `json:"kid"`
	}
	if err := decodeSegment(parts[0], &header); err != nil {
		return nil, fmt.Errorf("decode header: %w", err)
	}
	if header.Alg != "RS256" {
		return nil, fmt.Errorf("unexpected alg %q", header.Alg)
	}

	pub, err := v.keyFor(header.Kid)
	if err != nil {
		return nil, err
	}
	sig, err := base64.RawURLEncoding.DecodeString(parts[2])
	if err != nil {
		return nil, fmt.Errorf("decode signature: %w", err)
	}
	hashed := sha256.Sum256([]byte(parts[0] + "." + parts[1]))
	if err := rsa.VerifyPKCS1v15(pub, crypto.SHA256, hashed[:], sig); err != nil {
		return nil, errors.New("invalid token signature")
	}

	var claims Claims
	if err := decodeSegment(parts[1], &claims); err != nil {
		return nil, fmt.Errorf("decode claims: %w", err)
	}
	if claims.Expiry != 0 && time.Now().After(time.Unix(claims.Expiry, 0)) {
		return nil, errors.New("token expired")
	}
	if v.issuer != "" && claims.Issuer != v.issuer {
		return nil, fmt.Errorf("unexpected issuer %q", claims.Issuer)
	}
	return &claims, nil
}

func decodeSegment(seg string, v any) error {
	raw, err := base64.RawURLEncoding.DecodeString(seg)
	if err != nil {
		return err
	}
	return json.Unmarshal(raw, v)
}

func rsaPublicKey(nStr, eStr string) (*rsa.PublicKey, error) {
	nBytes, err := base64.RawURLEncoding.DecodeString(nStr)
	if err != nil {
		return nil, err
	}
	eBytes, err := base64.RawURLEncoding.DecodeString(eStr)
	if err != nil {
		return nil, err
	}
	e := 0
	for _, b := range eBytes {
		e = e<<8 | int(b)
	}
	if e == 0 {
		return nil, errors.New("invalid exponent")
	}
	return &rsa.PublicKey{N: new(big.Int).SetBytes(nBytes), E: e}, nil
}
