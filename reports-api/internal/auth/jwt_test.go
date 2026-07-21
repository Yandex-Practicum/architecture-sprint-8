package auth

import (
	"crypto"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"math/big"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

const testIssuer = "http://localhost:8080/realms/reports-realm"

func b64(b []byte) string { return base64.RawURLEncoding.EncodeToString(b) }

func signToken(t *testing.T, key *rsa.PrivateKey, kid string, claims map[string]any) string {
	t.Helper()
	header, _ := json.Marshal(map[string]any{"alg": "RS256", "typ": "JWT", "kid": kid})
	payload, _ := json.Marshal(claims)
	signingInput := b64(header) + "." + b64(payload)
	sum := sha256.Sum256([]byte(signingInput))
	sig, err := rsa.SignPKCS1v15(rand.Reader, key, crypto.SHA256, sum[:])
	if err != nil {
		t.Fatalf("sign: %v", err)
	}
	return signingInput + "." + b64(sig)
}

// newTestVerifier spins a JWKS server backed by a fresh RSA key.
func newTestVerifier(t *testing.T) (*Verifier, *rsa.PrivateKey, string) {
	t.Helper()
	key, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatalf("keygen: %v", err)
	}
	kid := "test-key-1"
	jwksJSON, _ := json.Marshal(map[string]any{
		"keys": []map[string]any{{
			"kid": kid, "kty": "RSA", "alg": "RS256", "use": "sig",
			"n": b64(key.PublicKey.N.Bytes()),
			"e": b64(big.NewInt(int64(key.PublicKey.E)).Bytes()),
		}},
	})
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Write(jwksJSON)
	}))
	t.Cleanup(srv.Close)
	return NewVerifier(srv.URL, testIssuer, srv.Client()), key, kid
}

func validClaims() map[string]any {
	return map[string]any{
		"sub":                "u-1",
		"preferred_username": "prothetic1",
		"iss":                testIssuer,
		"exp":                time.Now().Add(time.Minute).Unix(),
		"realm_access":       map[string]any{"roles": []string{"prothetic_user"}},
	}
}

func TestVerifyValidToken(t *testing.T) {
	v, key, kid := newTestVerifier(t)
	token := signToken(t, key, kid, validClaims())
	claims, err := v.Verify(token)
	if err != nil {
		t.Fatalf("Verify: %v", err)
	}
	if claims.PreferredUsername != "prothetic1" {
		t.Errorf("username: %q", claims.PreferredUsername)
	}
	if !claims.HasRole("prothetic_user") {
		t.Errorf("expected prothetic_user role")
	}
}

func TestVerifyRejectsTamperedSignature(t *testing.T) {
	v, key, kid := newTestVerifier(t)
	token := signToken(t, key, kid, validClaims())
	// flip the last character of the payload segment
	tampered := []byte(token)
	dot := 0
	for i, c := range tampered {
		if c == '.' {
			dot++
			if dot == 2 {
				tampered[i-1] ^= 0x01
				break
			}
		}
	}
	if _, err := v.Verify(string(tampered)); err == nil {
		t.Fatal("expected verification to fail for tampered token")
	}
}

func TestVerifyRejectsExpired(t *testing.T) {
	v, key, kid := newTestVerifier(t)
	c := validClaims()
	c["exp"] = time.Now().Add(-time.Minute).Unix()
	if _, err := v.Verify(signToken(t, key, kid, c)); err == nil {
		t.Fatal("expected expired token to be rejected")
	}
}

func TestVerifyRejectsWrongIssuer(t *testing.T) {
	v, key, kid := newTestVerifier(t)
	c := validClaims()
	c["iss"] = "http://evil/realms/x"
	if _, err := v.Verify(signToken(t, key, kid, c)); err == nil {
		t.Fatal("expected wrong issuer to be rejected")
	}
}

func TestVerifyRejectsNonRS256(t *testing.T) {
	v, _, _ := newTestVerifier(t)
	// alg=none style token
	header := b64([]byte(`{"alg":"none","typ":"JWT","kid":"test-key-1"}`))
	payload := b64([]byte(`{"sub":"x"}`))
	if _, err := v.Verify(header + "." + payload + "."); err == nil {
		t.Fatal("expected non-RS256 token to be rejected")
	}
}
