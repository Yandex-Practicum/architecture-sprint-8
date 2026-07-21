package httpapi

import (
	"context"
	"crypto/rand"
	"crypto/rsa"
	"encoding/json"
	"io"
	"math/big"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/bionicpro/reports-api/internal/auth"
	"github.com/bionicpro/reports-api/internal/clickhouse"
	"github.com/bionicpro/reports-api/internal/reports"
)

// fakeStore is an in-memory ObjectStore for cache-aside tests.
type fakeStore struct {
	mu   sync.Mutex
	m    map[string][]byte
	puts int
}

func newFakeStore() *fakeStore { return &fakeStore{m: make(map[string][]byte)} }

func (f *fakeStore) Exists(_ context.Context, key string) (bool, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	_, ok := f.m[key]
	return ok, nil
}

func (f *fakeStore) Put(_ context.Context, key string, body []byte, _ string) error {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.m[key] = body
	f.puts++
	return nil
}

// cacheServer wires a Server with the cache enabled plus a ClickHouse mock that
// counts how many times the expensive per-user rows query is executed.
func cacheServer(t *testing.T) (*Server, *rsa.PrivateKey, string, *fakeStore, *int32) {
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

	var rowsQueries int32
	ch := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		if strings.Contains(string(body), "max(report_date)") {
			w.Write([]byte(`{"data":[{"latest":"2026-07-19"}]}`))
			return
		}
		atomic.AddInt32(&rowsQueries, 1)
		w.Write([]byte(`{"data":[{"date":"2026-07-19","telemetry_events":10,"avg_response_ms":80,"max_response_ms":100,"avg_signal_quality":0.9,"total_movements":50,"avg_battery_pct":70,"full_name":"P One","prosthesis_serial":"BP-1001","region":"RU"}]}`))
	}))
	t.Cleanup(ch.Close)

	store := newFakeStore()
	verifier := auth.NewVerifier(jwks.URL, issuer, jwks.Client())
	builder := reports.NewBuilder(clickhouse.New(ch.URL, "default", "", ch.Client()), "reports", "user_report_mart", true)
	srv := New(verifier, builder, Options{
		RequiredRole: "prothetic_user",
		Timeout:      5 * time.Second,
		Store:        store,
		Bucket:       "reports",
		CDNBaseURL:   "http://cdn.local",
		URLSecret:    "sig-secret",
	})
	return srv, key, kid, store, &rowsQueries
}

func TestCacheMissThenHitSkipsOLAP(t *testing.T) {
	s, key, kid, store, rows := cacheServer(t)
	tok := sign(t, key, kid, claims("prothetic1", "prothetic_user"))

	// First call → cache miss: builds the report (1 OLAP rows query) and stores it.
	rr := do(t, s, "/reports", tok)
	if rr.Code != http.StatusOK {
		t.Fatalf("miss: got %d (%s)", rr.Code, rr.Body.String())
	}
	var link reportLink
	json.Unmarshal(rr.Body.Bytes(), &link)
	if link.Cached {
		t.Error("first response must not be cached")
	}
	if !strings.HasPrefix(link.ReportURL, "http://cdn.local/reports/prothetic1/") {
		t.Errorf("unexpected CDN url: %s", link.ReportURL)
	}
	if store.puts != 1 {
		t.Errorf("expected 1 object stored, got %d", store.puts)
	}
	if atomic.LoadInt32(rows) != 1 {
		t.Fatalf("expected 1 OLAP rows query on miss, got %d", *rows)
	}

	// Second identical call → cache hit: NO OLAP rows query, no new object.
	rr2 := do(t, s, "/reports", tok)
	if rr2.Code != http.StatusOK {
		t.Fatalf("hit: got %d", rr2.Code)
	}
	var link2 reportLink
	json.Unmarshal(rr2.Body.Bytes(), &link2)
	if !link2.Cached {
		t.Error("second response must be served from cache")
	}
	if link2.ReportURL != link.ReportURL {
		t.Errorf("cache url changed: %s vs %s", link.ReportURL, link2.ReportURL)
	}
	if store.puts != 1 {
		t.Errorf("cache hit must not store again, puts=%d", store.puts)
	}
	if atomic.LoadInt32(rows) != 1 {
		t.Fatalf("cache hit must NOT query OLAP again, rows=%d", *rows)
	}
}

func TestCacheKeyChangesWithWatermark(t *testing.T) {
	s, _, _, _, _ := cacheServer(t)
	k1 := s.objectKey("prothetic1", "", "", "2026-07-18")
	k2 := s.objectKey("prothetic1", "", "", "2026-07-19")
	if k1 == k2 {
		t.Fatal("object key must change when the ETL watermark advances (cache invalidation)")
	}
	// Deterministic for identical inputs (enables reuse).
	if s.objectKey("prothetic1", "", "", "2026-07-19") != k2 {
		t.Fatal("object key must be deterministic")
	}
	// Different users get different keys.
	if s.objectKey("prothetic2", "", "", "2026-07-19") == k2 {
		t.Fatal("different users must not share a key")
	}
}

func TestCacheStillEnforcesSelfOnly(t *testing.T) {
	s, key, kid, _, rows := cacheServer(t)
	tok := sign(t, key, kid, claims("prothetic1", "prothetic_user"))
	rr := do(t, s, "/reports?user=prothetic2", tok)
	if rr.Code != http.StatusForbidden {
		t.Fatalf("cross-user with cache: got %d, want 403", rr.Code)
	}
	if atomic.LoadInt32(rows) != 0 {
		t.Errorf("forbidden request must not touch OLAP, rows=%d", *rows)
	}
}
