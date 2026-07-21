package session

import (
	"testing"
	"time"
)

func TestReplaceRotatesIDAndKeepsLifetime(t *testing.T) {
	store := NewStore(30 * time.Minute)
	created, err := store.Create(Session{
		AccessToken:   "a",
		RefreshToken:  "r",
		RefreshExpiry: time.Now().Add(10 * time.Minute),
	})
	if err != nil {
		t.Fatalf("create: %v", err)
	}

	rotated, err := store.Replace(created.ID, created)
	if err != nil {
		t.Fatalf("replace: %v", err)
	}
	if rotated.ID == created.ID {
		t.Fatal("session id must change on rotation")
	}
	if !rotated.CreatedAt.Equal(created.CreatedAt) {
		t.Fatal("rotation must preserve the original creation time (session lifetime)")
	}
	// old id must be gone (fixation defense)
	if _, ok := store.Get(created.ID); ok {
		t.Fatal("old session id must be invalidated after rotation")
	}
	if _, ok := store.Get(rotated.ID); !ok {
		t.Fatal("new session id must be valid after rotation")
	}
}

func TestGetDropsExpiredSession(t *testing.T) {
	store := NewStore(time.Millisecond)
	created, _ := store.Create(Session{RefreshExpiry: time.Now().Add(time.Hour)})
	time.Sleep(5 * time.Millisecond)
	if _, ok := store.Get(created.ID); ok {
		t.Fatal("expired session must not be returned")
	}
}

func TestGetDropsWhenRefreshExpired(t *testing.T) {
	store := NewStore(time.Hour)
	created, _ := store.Create(Session{RefreshExpiry: time.Now().Add(-time.Second)})
	if _, ok := store.Get(created.ID); ok {
		t.Fatal("session with expired refresh token must not be returned")
	}
}
