package main

import (
	"context"
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"encoding/base64"
	"errors"
	"sync"
	"time"
)

type session struct {
	EncryptedRefresh []byte
	AccessToken      string
	Expiry           time.Time
	Username         string
	UserID           string
}

type sessionStore struct {
	gcm cipher.AEAD
	ttl time.Duration

	mu       sync.RWMutex
	sessions map[string]*session

	closeCh chan struct{}
}

func newSessionStore(encKey []byte, ttl time.Duration) *sessionStore {
	block, err := aes.NewCipher(encKey)
	if err != nil {
		panic("session: invalid encryption key: " + err.Error())
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		panic("session: gcm init: " + err.Error())
	}
	s := &sessionStore{
		gcm:      gcm,
		ttl:      ttl,
		sessions: make(map[string]*session),
		closeCh:  make(chan struct{}),
	}
	go s.gc()
	return s
}

func (s *sessionStore) Close() { close(s.closeCh) }

func newSessionID() (string, error) {
	buf := make([]byte, 32)
	if _, err := rand.Read(buf); err != nil {
		return "", err
	}
	return base64.RawURLEncoding.EncodeToString(buf), nil
}

func (s *sessionStore) encryptRefresh(plaintext []byte) ([]byte, error) {
	nonce := make([]byte, s.gcm.NonceSize())
	if _, err := rand.Read(nonce); err != nil {
		return nil, err
	}
	return s.gcm.Seal(nonce, nonce, plaintext, nil), nil
}

func (s *sessionStore) decryptRefresh(ciphertext []byte) ([]byte, error) {
	ns := s.gcm.NonceSize()
	if len(ciphertext) < ns {
		return nil, errors.New("session: ciphertext too short")
	}
	nonce, sealed := ciphertext[:ns], ciphertext[ns:]
	return s.gcm.Open(nil, nonce, sealed, nil)
}

func (s *sessionStore) create(p *tokenPair) (string, *session, error) {
	id, err := newSessionID()
	if err != nil {
		return "", nil, err
	}
	encRefresh, err := s.encryptRefresh([]byte(p.RefreshToken))
	if err != nil {
		return "", nil, err
	}
	sess := &session{
		EncryptedRefresh: encRefresh,
		AccessToken:      p.AccessToken,
		Expiry:           p.Expiry,
	}
	if sub, _ := p.Claims["sub"].(string); sub != "" {
		sess.UserID = sub
	}
	if name, _ := p.Claims["preferred_username"].(string); name != "" {
		sess.Username = name
	}
	s.mu.Lock()
	s.sessions[id] = sess
	s.mu.Unlock()
	return id, sess, nil
}

func (s *sessionStore) get(id string) (*session, bool) {
	s.mu.RLock()
	sess, ok := s.sessions[id]
	s.mu.RUnlock()
	return sess, ok
}

func (s *sessionStore) rotate(oldID string) (string, *session, error) {
	s.mu.Lock()
	sess, ok := s.sessions[oldID]
	if !ok {
		s.mu.Unlock()
		return "", nil, errors.New("session: not found")
	}
	delete(s.sessions, oldID)
	s.mu.Unlock()

	newID, err := newSessionID()
	if err != nil {
		return "", nil, err
	}
	rotated := &session{
		EncryptedRefresh: append([]byte{}, sess.EncryptedRefresh...),
		AccessToken:      sess.AccessToken,
		Expiry:           sess.Expiry,
		Username:         sess.Username,
		UserID:           sess.UserID,
	}
	s.mu.Lock()
	s.sessions[newID] = rotated
	s.mu.Unlock()
	return newID, rotated, nil
}

func (s *sessionStore) updateTokens(id string, p *tokenPair) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	sess, ok := s.sessions[id]
	if !ok {
		return errors.New("session: not found")
	}
	enc, err := s.encryptRefresh([]byte(p.RefreshToken))
	if err != nil {
		return err
	}
	sess.AccessToken = p.AccessToken
	sess.EncryptedRefresh = enc
	sess.Expiry = p.Expiry
	return nil
}

func (s *sessionStore) delete(id string) {
	s.mu.Lock()
	delete(s.sessions, id)
	s.mu.Unlock()
}

func (s *sessionStore) decryptedRefresh(sess *session) (string, error) {
	raw, err := s.decryptRefresh(sess.EncryptedRefresh)
	if err != nil {
		return "", err
	}
	return string(raw), nil
}

func (s *sessionStore) gc() {
	t := time.NewTicker(time.Minute)
	defer t.Stop()
	for {
		select {
		case <-s.closeCh:
			return
		case now := <-t.C:
			s.mu.Lock()
			for id, sess := range s.sessions {
				if now.After(sess.Expiry) {
					delete(s.sessions, id)
				}
			}
			s.mu.Unlock()
		}
	}
}

func (s *sessionStore) ensureFreshAccess(ctx context.Context, id string, kx *keycloakClient, skew time.Duration) (string, error) {
	s.mu.RLock()
	sess, ok := s.sessions[id]
	s.mu.RUnlock()
	if !ok {
		return "", errors.New("session: not found")
	}
	if time.Until(sess.Expiry) > skew {
		return sess.AccessToken, nil
	}
	refresh, err := s.decryptedRefresh(sess)
	if err != nil {
		return "", err
	}
	p, err := kx.refresh(ctx, refresh)
	if err != nil {
		return "", err
	}
	if err := s.updateTokens(id, p); err != nil {
		return "", err
	}
	return p.AccessToken, nil
}