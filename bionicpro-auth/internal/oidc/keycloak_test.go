package oidc

import (
	"crypto/sha256"
	"encoding/base64"
	"net/url"
	"strings"
	"testing"
)

func TestGeneratePKCEChallengeMatchesVerifier(t *testing.T) {
	verifier, challenge, err := GeneratePKCE()
	if err != nil {
		t.Fatalf("GeneratePKCE: %v", err)
	}
	sum := sha256.Sum256([]byte(verifier))
	want := base64.RawURLEncoding.EncodeToString(sum[:])
	if challenge != want {
		t.Fatalf("challenge %q does not match S256(verifier) %q", challenge, want)
	}
	if verifier == challenge {
		t.Fatal("verifier and challenge must differ")
	}
}

func TestAuthorizationURLUsesS256(t *testing.T) {
	c := New("http://localhost:8080", "http://keycloak:8080", "reports-realm",
		"bionicpro-auth", "secret", "http://localhost:8000/auth/callback")
	raw := c.AuthorizationURL("state123", "challenge123")
	if !strings.HasPrefix(raw, "http://localhost:8080/realms/reports-realm/protocol/openid-connect/auth?") {
		t.Fatalf("unexpected authorize base: %s", raw)
	}
	u, err := url.Parse(raw)
	if err != nil {
		t.Fatalf("parse: %v", err)
	}
	q := u.Query()
	if q.Get("code_challenge_method") != "S256" {
		t.Errorf("expected S256, got %q", q.Get("code_challenge_method"))
	}
	if q.Get("code_challenge") != "challenge123" {
		t.Errorf("challenge not forwarded")
	}
	if q.Get("response_type") != "code" {
		t.Errorf("expected authorization code flow")
	}
	if q.Get("client_id") != "bionicpro-auth" {
		t.Errorf("wrong client_id")
	}
}

func TestParseClaims(t *testing.T) {
	// {"sub":"u1","preferred_username":"prothetic1","email":"p1@example.com",
	//  "realm_access":{"roles":["prothetic_user"]}}
	payload := `{"sub":"u1","preferred_username":"prothetic1","email":"p1@example.com","realm_access":{"roles":["prothetic_user"]}}`
	token := "h." + base64.RawURLEncoding.EncodeToString([]byte(payload)) + ".sig"
	claims, err := ParseClaims(token)
	if err != nil {
		t.Fatalf("ParseClaims: %v", err)
	}
	if claims.PreferredUsername != "prothetic1" {
		t.Errorf("username: got %q", claims.PreferredUsername)
	}
	if len(claims.RealmAccess.Roles) != 1 || claims.RealmAccess.Roles[0] != "prothetic_user" {
		t.Errorf("roles not parsed: %v", claims.RealmAccess.Roles)
	}
}
