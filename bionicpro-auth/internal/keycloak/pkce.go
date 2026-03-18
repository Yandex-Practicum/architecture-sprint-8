package keycloak

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
)

type PKCEPair struct {
	Verifier  string
	Challenge string
	Method    string
}

func NewPKCEPair() (*PKCEPair, error) {
	verifier, err := randomBase64URL(64)
	if err != nil {
		return nil, err
	}

	sum := sha256.Sum256([]byte(verifier))
	challenge := base64.RawURLEncoding.EncodeToString(sum[:])

	return &PKCEPair{
		Verifier:  verifier,
		Challenge: challenge,
		Method:    "S256",
	}, nil
}

func randomBase64URL(n int) (string, error) {
	b := make([]byte, n)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	return base64.RawURLEncoding.EncodeToString(b), nil
}
