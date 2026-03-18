package session

import (
	"context"
	"crypto/rand"
	"encoding/base64"
	"errors"
	"time"

	enc "bionicpro-auth/internal/crypto"
	"bionicpro-auth/internal/keycloak"
)

type TokenRefresher interface {
	Refresh(ctx context.Context, refreshToken string) (*keycloak.TokenResponse, error)
}

type Manager struct {
	store             *Store
	cipher            *enc.Cipher
	refresher         TokenRefresher
	sessionTTL        time.Duration
	accessTokenLeeway time.Duration
}

func NewManager(store *Store, cipher *enc.Cipher, refresher TokenRefresher, sessionTTL, accessTokenLeeway time.Duration) *Manager {
	return &Manager{
		store:             store,
		cipher:            cipher,
		refresher:         refresher,
		sessionTTL:        sessionTTL,
		accessTokenLeeway: accessTokenLeeway,
	}
}

func (m *Manager) New(accessToken string, accessExp time.Time, refreshToken string) (*Session, error) {
	encRefresh, nonce, err := m.cipher.Encrypt([]byte(refreshToken))
	if err != nil {
		return nil, err
	}

	now := time.Now()
	sess := &Session{
		ID:                    randomID(32),
		AccessToken:           accessToken,
		AccessTokenExpiresAt:  accessExp,
		EncryptedRefreshToken: encRefresh,
		RefreshNonce:          nonce,
		CreatedAt:             now,
		ExpiresAt:             now.Add(m.sessionTTL),
		LastRotatedAt:         now,
	}
	m.store.Put(sess)
	return sess, nil
}

func (m *Manager) Get(id string) (*Session, bool) {
	return m.store.Get(id)
}

func (m *Manager) Delete(id string) {
	m.store.Delete(id)
}

func (m *Manager) ValidateAndRotate(ctx context.Context, sessionID string) (*Session, error) {
	sess, ok := m.store.Get(sessionID)
	if !ok {
		return nil, errors.New("session not found")
	}

	now := time.Now()
	if now.After(sess.ExpiresAt) {
		m.store.Delete(sess.ID)
		return nil, errors.New("session expired")
	}

	if now.After(sess.AccessTokenExpiresAt.Add(-m.accessTokenLeeway)) {
		refreshBytes, err := m.cipher.Decrypt(sess.EncryptedRefreshToken, sess.RefreshNonce)
		if err != nil {
			return nil, err
		}

		tokenResp, err := m.refresher.Refresh(ctx, string(refreshBytes))
		if err != nil {
			m.store.Delete(sess.ID)
			return nil, err
		}

		sess.AccessToken = tokenResp.AccessToken
		sess.AccessTokenExpiresAt = now.Add(time.Duration(tokenResp.ExpiresIn) * time.Second)

		if tokenResp.RefreshToken != "" {
			encRefresh, nonce, err := m.cipher.Encrypt([]byte(tokenResp.RefreshToken))
			if err != nil {
				return nil, err
			}
			sess.EncryptedRefreshToken = encRefresh
			sess.RefreshNonce = nonce
		}
	}

	next := &Session{
		ID:                    randomID(32),
		AccessToken:           sess.AccessToken,
		AccessTokenExpiresAt:  sess.AccessTokenExpiresAt,
		EncryptedRefreshToken: sess.EncryptedRefreshToken,
		RefreshNonce:          sess.RefreshNonce,
		CreatedAt:             sess.CreatedAt,
		ExpiresAt:             sess.ExpiresAt,
		LastRotatedAt:         now,
	}

	m.store.Rotate(sess.ID, next)
	return next, nil
}

func randomID(n int) string {
	b := make([]byte, n)
	_, _ = rand.Read(b)
	return base64.RawURLEncoding.EncodeToString(b)
}
