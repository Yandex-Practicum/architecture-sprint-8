package session

import "time"

type Session struct {
	ID                    string
	UserID                string
	AccessToken           string
	AccessTokenExpiresAt  time.Time
	EncryptedRefreshToken []byte
	RefreshNonce          []byte
	CreatedAt             time.Time
	ExpiresAt             time.Time
	LastRotatedAt         time.Time
}
