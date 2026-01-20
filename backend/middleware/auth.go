package middleware

import (
	"log"
	"net/http"
	"strings"

	"github.com/coreos/go-oidc/v3/oidc"
)

func AuthMiddleware(verifier *oidc.IDTokenVerifier, requiredRole string) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			auth := r.Header.Get("Authorization")
			if auth == "" {
				log.Printf("auth error: Authorization header missing")
				http.Error(w, "Authorization header missing", http.StatusUnauthorized)
				return
			}
			parts := strings.SplitN(auth, " ", 2)
			if len(parts) != 2 || !strings.EqualFold(parts[0], "Bearer") {
				log.Printf("auth error: invalid header format: %q", auth)
				http.Error(w, "Authorization header format must be Bearer {token}", http.StatusUnauthorized)
				return
			}
			rawToken := parts[1]

			idToken, err := verifier.Verify(r.Context(), rawToken)
			if err != nil {
				log.Printf("auth error: token verification failed: %v", err)
				http.Error(w, "Invalid or expired token", http.StatusUnauthorized)
				return
			}

			var claims struct {
				RealmAccess struct {
					Roles []string `json:"roles"`
				} `json:"realm_access"`
			}
			if err = idToken.Claims(&claims); err != nil {
				log.Printf("auth error: claims parsing failed: %v", err)
				http.Error(w, "Invalid token claims", http.StatusUnauthorized)
				return
			}

			for _, role := range claims.RealmAccess.Roles {
				if role == requiredRole {
					next.ServeHTTP(w, r)
					return
				}
			}
			log.Printf("auth error: missing required role %q, roles: %v", requiredRole, claims.RealmAccess.Roles)
			http.Error(w, "Forbidden: missing required role", http.StatusForbidden)
		})
	}
}
