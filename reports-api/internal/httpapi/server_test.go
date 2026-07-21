package httpapi

import (
	"crypto"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"io"
	"math/big"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/bionicpro/reports-api/internal/auth"
	"github.com/bionicpro/reports-api/internal/clickhouse"
	"github.com/bionicpro/reports-api/internal/reports"
)

const issuer = "http://kc/realms/reports-realm"

func b64(b []byte) string { return base64.RawURLEncoding.EncodeToString(b) }

func sign(t *testing.T, key *rsa.PrivateKey, kid string, claims map[string]any) string {
	t.Helper()
	header, _ := json.Marshal(map[string]any{"alg": "RS256", "typ": "JWT", "kid": kid})
	payload, _ := json.Marshal(claims)
	in := b64(header) + "." + b64(payload)
	sum := sha256.Sum256([]byte(in))
	sig, _ := rsa.SignPKCS1v15(rand.Reader, key, crypto.SHA256, sum[:])
	return in + "." + b64(sig)
}

// testServer wires a Server with a JWKS mock and a ClickHouse mock.
func testServer(t *testing.T) (*Server, *rsa.PrivateKey, string) {
	t.Helper()
	key, _ := rsa.GenerateKey(rand.Reader, 2048)
	kid := "k1"
	jwksJSON, _ := json.Marshal(map[string]any{"keys": []map[string]any{{
		"kid": kid, "kty": "RSA", "alg": "RS256", "use": "sig",
		"n": b64(key.PublicKey.N.Bytes()),
		"e": b64(big.NewInt(int64(key.PublicKey.E)).Bytes()),
	}}})
	jwks := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { w.Write(jwksJSON) }))
	t.Cleanup(jwks.Close)

	// Mock ClickHouse: distinguishes the watermark query from the rows query.
	ch := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		if strings.Contains(string(body), "max(report_date)") {
			w.Write([]byte(`{"data":[{"latest":"2026-07-19"}]}`))
			return
		}
		w.Write([]byte(`{"data":[
			{"date":"2026-07-18","telemetry_events":120,"avg_response_ms":82.5,"max_response_ms":140,"avg_signal_quality":0.91,"total_movements":540,"avg_battery_pct":73.2,"full_name":"Prothetic One","prosthesis_serial":"BP-0001","region":"RU"},
			{"date":"2026-07-19","telemetry_events":80,"avg_response_ms":90.0,"max_response_ms":150,"avg_signal_quality":0.88,"total_movements":300,"avg_battery_pct":69.0,"full_name":"Prothetic One","prosthesis_serial":"BP-0001","region":"RU"}
		]}`))
	}))
	t.Cleanup(ch.Close)

	verifier := auth.NewVerifier(jwks.URL, issuer, jwks.Client())
	builder := reports.NewBuilder(clickhouse.New(ch.URL, "default", "", ch.Client()), "reports", "user_report_mart", true)
	return New(verifier, builder, Options{RequiredRole: "prothetic_user", Timeout: 5 * time.Second}), key, kid
}

func claims(user string, roles ...string) map[string]any {
	return map[string]any{
		"sub": "u-" + user, "preferred_username": user, "iss": issuer,
		"exp":          time.Now().Add(time.Minute).Unix(),
		"realm_access": map[string]any{"roles": roles},
	}
}

func do(t *testing.T, s *Server, target, bearer string) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest(http.MethodGet, target, nil)
	if bearer != "" {
		req.Header.Set("Authorization", "Bearer "+bearer)
	}
	rr := httptest.NewRecorder()
	s.Handler().ServeHTTP(rr, req)
	return rr
}

func TestReportsRequiresAuth(t *testing.T) {
	s, _, _ := testServer(t)
	if rr := do(t, s, "/reports", ""); rr.Code != http.StatusUnauthorized {
		t.Fatalf("no token: got %d, want 401", rr.Code)
	}
	if rr := do(t, s, "/reports", "garbage.token.here"); rr.Code != http.StatusUnauthorized {
		t.Fatalf("bad token: got %d, want 401", rr.Code)
	}
}

func TestReportsForbidsOtherUser(t *testing.T) {
	s, key, kid := testServer(t)
	tok := sign(t, key, kid, claims("prothetic1", "prothetic_user"))
	rr := do(t, s, "/reports?user=prothetic2", tok)
	if rr.Code != http.StatusForbidden {
		t.Fatalf("cross-user access: got %d, want 403", rr.Code)
	}
}

func TestReportsForbidsMissingRole(t *testing.T) {
	s, key, kid := testServer(t)
	tok := sign(t, key, kid, claims("user1", "user"))
	rr := do(t, s, "/reports", tok)
	if rr.Code != http.StatusForbidden {
		t.Fatalf("missing role: got %d, want 403", rr.Code)
	}
}

func TestReportsReturnsOwnReport(t *testing.T) {
	s, key, kid := testServer(t)
	tok := sign(t, key, kid, claims("prothetic1", "prothetic_user"))
	rr := do(t, s, "/reports", tok)
	if rr.Code != http.StatusOK {
		t.Fatalf("own report: got %d, want 200 (body: %s)", rr.Code, rr.Body.String())
	}
	var rep reports.Report
	if err := json.Unmarshal(rr.Body.Bytes(), &rep); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if rep.Username != "prothetic1" {
		t.Errorf("username: %q", rep.Username)
	}
	if len(rep.Days) != 2 {
		t.Errorf("days: got %d, want 2", len(rep.Days))
	}
	if rep.Summary.TotalEvents != 200 {
		t.Errorf("total events: got %d, want 200", rep.Summary.TotalEvents)
	}
	if rep.LatestProcessedDate != "2026-07-19" {
		t.Errorf("watermark: %q", rep.LatestProcessedDate)
	}
}

func TestReportsNoticeBeyondWatermark(t *testing.T) {
	s, key, kid := testServer(t)
	tok := sign(t, key, kid, claims("prothetic1", "prothetic_user"))
	rr := do(t, s, "/reports?to=2030-01-01", tok)
	if rr.Code != http.StatusOK {
		t.Fatalf("got %d", rr.Code)
	}
	var rep reports.Report
	json.Unmarshal(rr.Body.Bytes(), &rep)
	if rep.Notice == "" {
		t.Error("expected a notice when requesting data beyond the processed watermark")
	}
}
