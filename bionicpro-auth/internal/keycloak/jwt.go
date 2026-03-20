package keycloak

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"strings"
)

type TokenClaims struct {
	Sub string `json:"sub"`
}

func ExtractSubFromAccessToken(token string) (string, error) {
	parts := strings.Split(token, ".")
	if len(parts) < 2 {
		return "", fmt.Errorf("invalid token format")
	}
	payload, err := base64.RawURLEncoding.DecodeString(parts[1])
	if err != nil {
		return "", err
	}
	var claims TokenClaims
	if err := json.Unmarshal(payload, &claims); err != nil {
		return "", err
	}
	if claims.Sub == "" {
		return "", fmt.Errorf("sub is empty")
	}
	return claims.Sub, nil
}
