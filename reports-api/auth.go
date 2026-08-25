package main

import (
	"net/http"
	"slices"
	"strings"

	"github.com/MicahParks/keyfunc/v3"
	"github.com/golang-jwt/jwt/v5"
)

const reportsRole = "prothetic_user"

type claims struct {
	PreferredUsername string `json:"preferred_username"`
	RealmAccess       struct {
		Roles []string `json:"roles"`
	} `json:"realm_access"`
	jwt.RegisteredClaims
}

type authError struct {
	status  int
	message string
}

func (e authError) Error() string { return e.message }

type authenticator struct {
	keys   jwt.Keyfunc
	issuer string
}

func newAuthenticator(jwksURL, issuer string) (*authenticator, error) {
	jwks, err := keyfunc.NewDefault([]string{jwksURL})
	if err != nil {
		return nil, err
	}
	return &authenticator{keys: jwks.Keyfunc, issuer: issuer}, nil
}

func (a *authenticator) authenticate(r *http.Request) (string, error) {
	raw, ok := strings.CutPrefix(r.Header.Get("Authorization"), "Bearer ")
	if !ok || raw == "" {
		return "", authError{http.StatusUnauthorized, "bearer token is required"}
	}

	var c claims
	if _, err := jwt.ParseWithClaims(raw, &c, a.keys,
		jwt.WithValidMethods([]string{jwt.SigningMethodRS256.Name}),
		jwt.WithIssuer(a.issuer),
		jwt.WithExpirationRequired(),
	); err != nil {
		return "", authError{http.StatusUnauthorized, "invalid token"}
	}

	if !slices.Contains(c.RealmAccess.Roles, reportsRole) {
		return "", authError{http.StatusForbidden, "role " + reportsRole + " is required"}
	}
	if c.PreferredUsername == "" {
		return "", authError{http.StatusUnauthorized, "token has no preferred_username"}
	}
	return c.PreferredUsername, nil
}
