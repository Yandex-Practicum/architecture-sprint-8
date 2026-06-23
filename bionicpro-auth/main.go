package main

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"sync"
	"time"
)

var (
	keycloakBackendURL  string
	keycloakFrontendURL string
	clientID            string
	redirectURI         string
	frontendURL         string
	apiURL              string
)

func getEnv(key, fallback string) string {
	if value, ok := os.LookupEnv(key); ok {
		return value
	}
	return fallback
}

// Инициализация переменных окружения при старте
func init() {
	keycloakBackendURL = getEnv("KEYCLOAK_BACKEND_URL", "http://keycloak:8080/auth/realms/reports-realm")
	keycloakFrontendURL = getEnv("KEYCLOAK_FRONTEND_URL", "http://localhost:8080/auth/realms/reports-realm")
	clientID = getEnv("CLIENT_ID", "bionicpro-client")
	redirectURI = getEnv("REDIRECT_URI", "http://localhost:8081/callback")
	frontendURL = getEnv("FRONTEND_URL", "http://localhost:3000")
	apiURL = getEnv("API_URL", "http://localhost:8082")
}

type Session struct {
	AccessToken  string
	RefreshToken string
	ExpiresAt    time.Time
}

var (
	sessionStore = make(map[string]Session)
	pkceStore    = make(map[string]string) // map[state]code_verifier
	storeMutex   sync.RWMutex
)

func generateRandomString(length int) string {
	b := make([]byte, length)
	rand.Read(b)
	return base64.RawURLEncoding.EncodeToString(b)
}

func generateCodeChallenge(verifier string) string {
	s := sha256.Sum256([]byte(verifier))
	return base64.RawURLEncoding.EncodeToString(s[:])
}

// 1. Эндпоинт начала авторизации (Редирект в Keycloak)
func loginHandler(w http.ResponseWriter, r *http.Request) {
	state := generateRandomString(32)
	codeVerifier := generateRandomString(32)
	codeChallenge := generateCodeChallenge(codeVerifier)

	storeMutex.Lock()
	pkceStore[state] = codeVerifier
	storeMutex.Unlock()

	authURL := fmt.Sprintf("%s/protocol/openid-connect/auth?client_id=%s&response_type=code&redirect_uri=%s&state=%s&code_challenge=%s&code_challenge_method=S256",
		keycloakFrontendURL, clientID, redirectURI, state, codeChallenge)

	http.Redirect(w, r, authURL, http.StatusFound)
}

// 2. Эндпоинт обработки ответа от Keycloak (Обмен кода на токены)
func callbackHandler(w http.ResponseWriter, r *http.Request) {
	code := r.URL.Query().Get("code")
	state := r.URL.Query().Get("state")

	storeMutex.RLock()
	codeVerifier, exists := pkceStore[state]
	storeMutex.RUnlock()

	if !exists {
		http.Error(w, "State not found or expired", http.StatusBadRequest)
		return
	}

	storeMutex.Lock()
	delete(pkceStore, state)
	storeMutex.Unlock()

	data := url.Values{}
	data.Set("grant_type", "authorization_code")
	data.Set("client_id", clientID)
	data.Set("redirect_uri", redirectURI)
	data.Set("code", code)
	data.Set("code_verifier", codeVerifier)

	resp, err := http.PostForm(keycloakBackendURL+"/protocol/openid-connect/token", data)
	if err != nil || resp.StatusCode != 200 {
		http.Error(w, "Failed to exchange token", http.StatusInternalServerError)
		return
	}
	defer resp.Body.Close()

	var tokenResp struct {
		AccessToken  string `json:"access_token"`
		RefreshToken string `json:"refresh_token"`
		ExpiresIn    int    `json:"expires_in"`
	}
	json.NewDecoder(resp.Body).Decode(&tokenResp)

	sessionID := generateRandomString(32)
	storeMutex.Lock()
	sessionStore[sessionID] = Session{
		AccessToken:  tokenResp.AccessToken,
		RefreshToken: tokenResp.RefreshToken,
		ExpiresAt:    time.Now().Add(time.Duration(tokenResp.ExpiresIn) * time.Second),
	}
	storeMutex.Unlock()

	http.SetCookie(w, &http.Cookie{
		Name:     "session_id",
		Value:    sessionID,
		Path:     "/",
		HttpOnly: true,
		SameSite: http.SameSiteLaxMode,
		MaxAge:   86400, // 1 день
	})

	http.Redirect(w, r, frontendURL, http.StatusFound)
}

// 3. Middleware проксирования API и проверки/ротации сессии
func proxyMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		cookie, err := r.Cookie("session_id")
		if err != nil {
			http.Error(w, "Unauthorized", http.StatusUnauthorized)
			return
		}

		sessionID := cookie.Value
		storeMutex.RLock()
		session, exists := sessionStore[sessionID]
		storeMutex.RUnlock()

		if !exists {
			http.Error(w, "Unauthorized", http.StatusUnauthorized)
			return
		}

		if time.Now().After(session.ExpiresAt.Add(-10 * time.Second)) {
			data := url.Values{}
			data.Set("grant_type", "refresh_token")
			data.Set("client_id", clientID)
			data.Set("refresh_token", session.RefreshToken)

			resp, err := http.PostForm(keycloakBackendURL+"/protocol/openid-connect/token", data)
			if err != nil || resp.StatusCode != 200 {
				http.Error(w, "Failed to refresh token", http.StatusUnauthorized)
				return
			}
			defer resp.Body.Close()

			var refreshResp struct {
				AccessToken  string `json:"access_token"`
				RefreshToken string `json:"refresh_token"`
				ExpiresIn    int    `json:"expires_in"`
			}
			json.NewDecoder(resp.Body).Decode(&refreshResp)

			newSessionID := generateRandomString(32)

			storeMutex.Lock()
			delete(sessionStore, sessionID)
			sessionStore[newSessionID] = Session{
				AccessToken:  refreshResp.AccessToken,
				RefreshToken: refreshResp.RefreshToken,
				ExpiresAt:    time.Now().Add(time.Duration(refreshResp.ExpiresIn) * time.Second),
			}
			storeMutex.Unlock()

			http.SetCookie(w, &http.Cookie{
				Name:     "session_id",
				Value:    newSessionID,
				Path:     "/",
				HttpOnly: true,
				SameSite: http.SameSiteLaxMode,
				MaxAge:   86400,
			})
			sessionID = newSessionID
			session.AccessToken = refreshResp.AccessToken
		}

		r.Header.Set("Authorization", "Bearer "+session.AccessToken)
		next.ServeHTTP(w, r)
	})
}

func main() {
	http.HandleFunc("/login", loginHandler)
	http.HandleFunc("/callback", callbackHandler)

	apiProxyURL, _ := url.Parse(apiURL)
	proxy := httputil.NewSingleHostReverseProxy(apiProxyURL)

	http.Handle("/api/", proxyMiddleware(proxy))

	log.Println("bionicpro-auth service started on :8081")
	log.Fatal(http.ListenAndServe(":8081", nil))
}
