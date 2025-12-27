package http

import (
	"crypto/rsa"
	"fmt"
	"net/http"
	"strings"

	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
	"github.com/lestrrat-go/jwx/jwk"
)

func AuthMiddleware(jwkSet jwk.Set) gin.HandlerFunc {
	return func(c *gin.Context) {
		authHeader := c.GetHeader(authorizationHeader)
		if authHeader == "" {
			c.AbortWithStatusJSON(http.StatusUnauthorized, ErrorMessage{Error: "Authorization header is required"})
			return
		}

		tokenRaw := strings.TrimPrefix(authHeader, prefixTokenBearer)

		token, err := jwt.Parse(tokenRaw, func(token *jwt.Token) (interface{}, error) {
			if _, ok := token.Method.(*jwt.SigningMethodRSA); !ok {
				return nil, fmt.Errorf("unexpected signing method: %v", token.Header["alg"])
			}

			kid, isKidFound := token.Header["kid"].(string)
			if !isKidFound {
				return nil, fmt.Errorf("jwt token not contains kid")
			}

			key, isKeyFound := jwkSet.LookupKeyID(kid)
			if !isKeyFound {
				return nil, fmt.Errorf("jwk not contains key with kid from jwt: %s", kid)
			}

			var rawKey interface{}
			if err := key.Raw(&rawKey); err != nil {
				return nil, fmt.Errorf("key.Raw: %w", err)
			}

			rsaPubKey, ok := rawKey.(*rsa.PublicKey)
			if !ok {
				return nil, fmt.Errorf("jwk not contains rsa public key")
			}

			return rsaPubKey, nil
		})
		if err != nil {
			c.AbortWithStatusJSON(http.StatusUnauthorized, ErrorMessage{Error: fmt.Sprintf("invalid token: %s", err.Error())})
			return
		}

		claims, ok := token.Claims.(jwt.MapClaims)
		if !ok || !token.Valid {
			c.AbortWithStatusJSON(http.StatusUnauthorized, ErrorMessage{Error: "invalid token claims"})
			return
		}

		realmAccess, ok := claims["realm_access"].(map[string]interface{})
		if !ok {
			c.AbortWithStatusJSON(http.StatusUnauthorized, ErrorMessage{Error: "no realm_access in token"})
			return
		}

		roles, ok := realmAccess["roles"].([]interface{})
		if !ok {
			c.AbortWithStatusJSON(http.StatusUnauthorized, ErrorMessage{Error: "no roles in token"})
			return
		}

		c.Set("roles", roles)

		c.Next()
	}
}
