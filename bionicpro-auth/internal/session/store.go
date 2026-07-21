// Package session implements a server-side session store for the auth BFF.
//
// Sessions are the only thing the browser ever holds a reference to (via an
// opaque, HttpOnly+Secure cookie). Access and refresh tokens received from the
// IdP are kept here, on the server, and are never exposed to the frontend.
package session

import (
	"crypto/rand"
	"encoding/base64"
	"errors"
	"sync"
	"time"
)

// ErrNotFound is returned when a session id is unknown or has expired.
var ErrNotFound = errors.New("session not found")

// Session binds an access/refresh token pair to a single browser session.
type Session struct {
	ID            string
	AccessToken   string
	RefreshToken  string
	AccessExpiry  time.Time
	RefreshExpiry time.Time
	Subject       string
	Username      string
	Email         string
	Roles         []string
	CreatedAt     time.Time
}

// Store is an in-memory, concurrency-safe session store. In production this
// would be backed by a distributed cache (Redis); the interface stays the same.
type Store struct {
	mu  sync.Mutex
	m   map[string]Session
	ttl time.Duration
}

// NewStore creates a store whose sessions live at most ttl after creation.
func NewStore(ttl time.Duration) *Store {
	return &Store{m: make(map[string]Session), ttl: ttl}
}

// Create stores a new session and returns it with a freshly generated id.
func (s *Store) Create(sess Session) (Session, error) {
	id, err := newID()
	if err != nil {
		return Session{}, err
	}
	sess.ID = id
	sess.CreatedAt = time.Now()
	s.mu.Lock()
	s.m[id] = sess
	s.mu.Unlock()
	return sess, nil
}

// Get returns the session for id, transparently dropping it if the session TTL
// or the refresh token has expired (in which case a re-login is required).
func (s *Store) Get(id string) (Session, bool) {
	s.mu.Lock()
	defer s.mu.Unlock()
	sess, ok := s.m[id]
	if !ok {
		return Session{}, false
	}
	now := time.Now()
	if now.After(sess.CreatedAt.Add(s.ttl)) || now.After(sess.RefreshExpiry) {
		delete(s.m, id)
		return Session{}, false
	}
	return sess, true
}

// Replace atomically deletes oldID and re-stores the (possibly refreshed)
// session under a brand new id. This is the session-rotation primitive used to
// defend against session fixation: every authenticated request gets a new id
// while the original creation time — and therefore the session lifetime — is
// preserved.
func (s *Store) Replace(oldID string, sess Session) (Session, error) {
	newID, err := newID()
	if err != nil {
		return Session{}, err
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	existing, ok := s.m[oldID]
	if !ok {
		return Session{}, ErrNotFound
	}
	delete(s.m, oldID)
	sess.ID = newID
	sess.CreatedAt = existing.CreatedAt // keep the original lifetime
	s.m[newID] = sess
	return sess, nil
}

// Delete removes a session (used on logout).
func (s *Store) Delete(id string) {
	s.mu.Lock()
	delete(s.m, id)
	s.mu.Unlock()
}

// newID returns a 256-bit cryptographically random, URL-safe identifier.
func newID() (string, error) {
	b := make([]byte, 32)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	return base64.RawURLEncoding.EncodeToString(b), nil
}
