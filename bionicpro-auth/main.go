package main

import (
	"context"
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"database/sql"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/gin-contrib/sessions"
	"github.com/gin-contrib/sessions/cookie"
	"github.com/gin-gonic/gin"
	"github.com/go-redis/redis/v8"
	"github.com/google/uuid"
	"golang.org/x/oauth2"
	_ "modernc.org/sqlite"
)

const (
	sessionCookieName = "bionicpro_session"
	sessionMaxAge     = 3600 // 1 hour
)

var (
	keycloakConfig *oauth2.Config
	redisClient    *redis.Client
	encryptionKey  []byte
	profileDB      *sql.DB
)

type TokenData struct {
	AccessToken  string    `json:"access_token"`
	RefreshToken string    `json:"refresh_token"`
	ExpiresAt    time.Time `json:"expires_at"`
	SessionID    string    `json:"session_id"`
}

type SessionData struct {
	AccessToken  string    `json:"access_token"`
	RefreshToken string    `json:"refresh_token"`
	ExpiresAt    time.Time `json:"expires_at"`
	UserID       string    `json:"user_id"`
}

func init() {
	keycloakAuthURL := getEnv("KEYCLOAK_AUTH_URL", getEnv("KEYCLOAK_URL", "http://localhost:8080"))
	keycloakTokenURL := getEnv("KEYCLOAK_TOKEN_URL", getEnv("KEYCLOAK_URL", "http://localhost:8080"))
	keycloakRealm := getEnv("KEYCLOAK_REALM", "reports-realm")
	clientID := getEnv("KEYCLOAK_CLIENT_ID", "bionicpro-auth")
	clientSecret := getEnv("KEYCLOAK_CLIENT_SECRET", "bionicpro-auth-secret-change-in-production")
	redirectURL := getEnv("REDIRECT_URL", "http://localhost:8000/auth/callback")

	keycloakConfig = &oauth2.Config{
		ClientID:     clientID,
		ClientSecret: clientSecret,
		RedirectURL:  redirectURL,
		Scopes:       []string{"openid", "profile", "email"},
		Endpoint: oauth2.Endpoint{
			AuthURL:  fmt.Sprintf("%s/realms/%s/protocol/openid-connect/auth", keycloakAuthURL, keycloakRealm),
			TokenURL: fmt.Sprintf("%s/realms/%s/protocol/openid-connect/token", keycloakTokenURL, keycloakRealm),
		},
	}

	redisAddr := getEnv("REDIS_ADDR", "localhost:6379")
	redisClient = redis.NewClient(&redis.Options{
		Addr: redisAddr,
	})

	ctx := context.Background()
	if err := redisClient.Ping(ctx).Err(); err != nil {
		log.Printf("Warning: Redis connection failed: %v. Using in-memory storage.", err)
		redisClient = nil
	}

	encryptionKey = []byte(getEnv("ENCRYPTION_KEY", "change-this-32-byte-key!!"))
	if len(encryptionKey) != 32 {
		log.Fatal("ENCRYPTION_KEY must be exactly 32 bytes")
	}
}

func initProfileDB() {
	dbPath := getEnv("PROFILE_DB_PATH", "./data/profiles.db")
	if err := os.MkdirAll(filepath.Dir(dbPath), 0755); err != nil {
		log.Printf("Warning: could not create profile DB dir: %v", err)
		return
	}
	db, err := sql.Open("sqlite", dbPath)
	if err != nil {
		log.Printf("Warning: profile DB open failed: %v", err)
		return
	}
	profileDB = db
	_, _ = db.Exec(`
		CREATE TABLE IF NOT EXISTS user_profiles (
			keycloak_sub TEXT PRIMARY KEY,
			idp TEXT NOT NULL,
			email TEXT,
			first_name TEXT,
			last_name TEXT,
			yandex_id TEXT,
			profile_json TEXT,
			created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
			updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
		)
	`)
}

func main() {
	initProfileDB()
	r := gin.Default()

	// CORS: разрешаем фронт и бэкенд по localhost и 127.0.0.1, чтобы cookie с credentials отправлялись
	allowedOrigins := map[string]bool{
		"http://localhost:3000": true, "http://localhost:8000": true,
		"http://127.0.0.1:3000": true, "http://127.0.0.1:8000": true,
	}
	if frontendURL := getEnv("FRONTEND_URL", ""); frontendURL != "" {
		allowedOrigins[frontendURL] = true
	}
	r.Use(func(c *gin.Context) {
		origin := c.GetHeader("Origin")
		if allowedOrigins[origin] {
			c.Writer.Header().Set("Access-Control-Allow-Origin", origin)
			c.Writer.Header().Set("Access-Control-Allow-Credentials", "true")
			c.Writer.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
			c.Writer.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
		}

		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(204)
			return
		}

		c.Next()
	})

	store := cookie.NewStore([]byte(getEnv("SESSION_SECRET", "change-this-secret-key")))
	store.Options(sessions.Options{
		Path:     "/",
		MaxAge:   sessionMaxAge,
		HttpOnly: true,
		Secure:   false,
		SameSite: http.SameSiteLaxMode,
	})
	r.Use(sessions.Sessions(sessionCookieName, store))

	r.GET("/auth/login", handleLogin)
	r.GET("/auth/callback", handleCallback)
	r.GET("/auth/logout", handleLogout)
	r.GET("/auth/me", authMiddleware(), handleMe)

	api := r.Group("/api")
	api.Use(authMiddleware())
	{
		api.GET("/reports", handleReports)
	}

	log.Println("Starting server on :8000")
	if err := r.Run(":8000"); err != nil {
		log.Fatal(err)
	}
}

func handleLogin(c *gin.Context) {
	state := generateState()
	verifier := oauth2.GenerateVerifier()
	session := sessions.Default(c)
	session.Set("oauth_state", state)
	session.Set("code_verifier", verifier)
	if err := session.Save(); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to save session"})
		return
	}

	opts := []oauth2.AuthCodeOption{oauth2.AccessTypeOffline, oauth2.S256ChallengeOption(verifier)}
	url := keycloakConfig.AuthCodeURL(state, opts...)
	c.Redirect(http.StatusFound, url)
}

func handleCallback(c *gin.Context) {
	session := sessions.Default(c)
	storedState := session.Get("oauth_state")
	if storedState == nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Missing state"})
		return
	}

	state := c.Query("state")
	if state != storedState {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid state"})
		return
	}

	code := c.Query("code")
	if code == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Missing authorization code"})
		return
	}

	codeVerifier, _ := session.Get("code_verifier").(string)
	var exchangeOpts []oauth2.AuthCodeOption
	if codeVerifier != "" {
		exchangeOpts = append(exchangeOpts, oauth2.VerifierOption(codeVerifier))
	}

	ctx := c.Request.Context()
	token, err := keycloakConfig.Exchange(ctx, code, exchangeOpts...)
	if err != nil {
		log.Printf("Token exchange failed: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to exchange token", "details": err.Error()})
		return
	}

	sessionID := generateSessionID()
	expiresAt := time.Now().Add(2 * time.Minute)

	tokenData := &TokenData{
		AccessToken:  token.AccessToken,
		RefreshToken: token.RefreshToken,
		ExpiresAt:    expiresAt,
		SessionID:    sessionID,
	}

	if err = storeTokens(sessionID, tokenData); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to store tokens"})
		return
	}

	session.Set("session_id", sessionID)
	session.Delete("oauth_state")
	session.Delete("code_verifier")
	if err := session.Save(); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to save session"})
		return
	}

	saveUserProfileFromToken(token.AccessToken)

	frontendURL := getEnv("FRONTEND_URL", "http://localhost:3000")
	c.Redirect(http.StatusFound, frontendURL)
}

func handleLogout(c *gin.Context) {
	session := sessions.Default(c)
	sessionID := session.Get("session_id")
	if sessionID != nil {
		deleteTokens(sessionID.(string))
	}
	session.Clear()
	session.Save()

	frontendURL := getEnv("FRONTEND_URL", "http://localhost:3000")
	c.Redirect(http.StatusFound, frontendURL)
}

func handleMe(c *gin.Context) {
	userInfo, exists := c.Get("user_info")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "Unauthorized"})
		return
	}

	c.JSON(http.StatusOK, userInfo)
}

func handleReports(c *gin.Context) {
	sessionData := c.MustGet("session_data").(*SessionData)

	req, _ := http.NewRequest("GET", getEnv("REPORTS_API_URL", "http://localhost:9000/reports"), nil)
	req.Header.Set("Authorization", "Bearer "+sessionData.AccessToken)
	req.Header.Set("X-User-Id", sessionData.UserID)

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		log.Printf("reports api request failed: %v", err)
		c.JSON(http.StatusBadGateway, gin.H{
			"error":   "reports_unavailable",
			"message": "Сервис отчётов недоступен. Убедитесь, что reports-api и olap_db запущены.",
		})
		return
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	contentType := resp.Header.Get("Content-Type")
	if contentType == "" {
		contentType = "application/json"
	}
	c.Data(resp.StatusCode, contentType, body)
}

func authMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		session := sessions.Default(c)
		sessionID := session.Get("session_id")
		if sessionID == nil {
			c.JSON(http.StatusUnauthorized, gin.H{"error": "Unauthorized"})
			c.Abort()
			return
		}

		tokenData, err := getTokens(sessionID.(string))
		if err != nil {
			c.JSON(http.StatusUnauthorized, gin.H{"error": "Session not found"})
			c.Abort()
			return
		}

		var newTokenData *TokenData
		needsRefresh := time.Now().After(tokenData.ExpiresAt)

		if needsRefresh {
			newTokenData, err = refreshAccessToken(tokenData.RefreshToken)
			if err != nil {
				c.JSON(http.StatusUnauthorized, gin.H{"error": "Failed to refresh token"})
				c.Abort()
				return
			}
		} else {
			newTokenData = tokenData
		}

		// Session rotation: create new session ID on every request to prevent session fixation
		newSessionID := generateSessionID()
		newTokenData.SessionID = newSessionID

		if err := storeTokens(newSessionID, newTokenData); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to store new tokens"})
			c.Abort()
			return
		}

		// Delete old session
		deleteTokens(sessionID.(string))

		// Update session cookie with new session ID
		session.Set("session_id", newSessionID)
		if err := session.Save(); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to save session"})
			c.Abort()
			return
		}

		// Extract user info from access token
		userInfo := extractUserInfo(newTokenData.AccessToken)

		sessionData := &SessionData{
			AccessToken:  newTokenData.AccessToken,
			RefreshToken: newTokenData.RefreshToken,
			ExpiresAt:    newTokenData.ExpiresAt,
			UserID:       userInfo["sub"].(string),
		}

		c.Set("session_data", sessionData)
		c.Set("user_info", userInfo)
		c.Next()
	}
}

func refreshAccessToken(refreshToken string) (*TokenData, error) {
	ctx := context.Background()
	tokenSource := keycloakConfig.TokenSource(ctx, &oauth2.Token{
		RefreshToken: refreshToken,
	})

	newToken, err := tokenSource.Token()
	if err != nil {
		return nil, err
	}

	return &TokenData{
		AccessToken:  newToken.AccessToken,
		RefreshToken: newToken.RefreshToken,
		ExpiresAt:    time.Now().Add(2 * time.Minute),
	}, nil
}

func storeTokens(sessionID string, tokenData *TokenData) error {
	data, err := json.Marshal(tokenData)
	if err != nil {
		return err
	}

	encrypted, err := encrypt(data)
	if err != nil {
		return err
	}

	if redisClient != nil {
		ctx := context.Background()
		return redisClient.Set(ctx, "session:"+sessionID, encrypted, sessionMaxAge*time.Second).Err()
	}

	return nil
}

func getTokens(sessionID string) (*TokenData, error) {
	var encrypted string

	if redisClient != nil {
		ctx := context.Background()
		val, err := redisClient.Get(ctx, "session:"+sessionID).Result()
		if err != nil {
			return nil, err
		}
		encrypted = val
	} else {
		return nil, fmt.Errorf("no storage available")
	}

	decrypted, err := decrypt(encrypted)
	if err != nil {
		return nil, err
	}

	var tokenData TokenData
	if err := json.Unmarshal(decrypted, &tokenData); err != nil {
		return nil, err
	}

	return &tokenData, nil
}

func deleteTokens(sessionID string) {
	if redisClient != nil {
		ctx := context.Background()
		redisClient.Del(ctx, "session:"+sessionID)
	}
}

func encrypt(data []byte) (string, error) {
	block, err := aes.NewCipher(encryptionKey)
	if err != nil {
		return "", err
	}

	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return "", err
	}

	nonce := make([]byte, gcm.NonceSize())
	if _, err = io.ReadFull(rand.Reader, nonce); err != nil {
		return "", err
	}

	ciphertext := gcm.Seal(nonce, nonce, data, nil)
	return base64.StdEncoding.EncodeToString(ciphertext), nil
}

func decrypt(encrypted string) ([]byte, error) {
	data, err := base64.StdEncoding.DecodeString(encrypted)
	if err != nil {
		return nil, err
	}

	block, err := aes.NewCipher(encryptionKey)
	if err != nil {
		return nil, err
	}

	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return nil, err
	}

	nonceSize := gcm.NonceSize()
	if len(data) < nonceSize {
		return nil, fmt.Errorf("ciphertext too short")
	}

	nonce, ciphertext := data[:nonceSize], data[nonceSize:]
	plaintext, err := gcm.Open(nil, nonce, ciphertext, nil)
	if err != nil {
		return nil, err
	}

	return plaintext, nil
}

func generateState() string {
	return generateSessionID()
}

func generateSessionID() string {
	return uuid.NewString()
}

func extractUserInfo(accessToken string) map[string]interface{} {
	parts := strings.Split(accessToken, ".")
	if len(parts) != 3 {
		return make(map[string]interface{})
	}

	payload := parts[1]
	decoded, err := base64.RawURLEncoding.DecodeString(payload)
	if err != nil {
		return make(map[string]interface{})
	}

	var claims map[string]interface{}
	if err := json.Unmarshal(decoded, &claims); err != nil {
		return make(map[string]interface{})
	}

	return claims
}

// saveUserProfileFromToken persists user profile to DB when identity_provider is yandex (Identity Brokering).
func saveUserProfileFromToken(accessToken string) {
	if profileDB == nil {
		return
	}
	claims := extractUserInfo(accessToken)
	idp, _ := claims["identity_provider"].(string)
	if idp != "yandex" {
		return
	}
	sub, _ := claims["sub"].(string)
	if sub == "" {
		return
	}
	email, _ := claims["email"].(string)
	firstName, _ := claims["given_name"].(string)
	if firstName == "" {
		firstName, _ = claims["name"].(string)
	}
	lastName, _ := claims["family_name"].(string)
	yandexID, _ := claims["preferred_username"].(string)
	profileJSON, _ := json.Marshal(claims)
	now := time.Now().Format("2006-01-02 15:04:05")
	_, err := profileDB.Exec(`
		INSERT INTO user_profiles (keycloak_sub, idp, email, first_name, last_name, yandex_id, profile_json, created_at, updated_at)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
		ON CONFLICT(keycloak_sub) DO UPDATE SET
			idp=excluded.idp, email=excluded.email, first_name=excluded.first_name, last_name=excluded.last_name,
			yandex_id=excluded.yandex_id, profile_json=excluded.profile_json, updated_at=excluded.updated_at
	`, sub, idp, email, firstName, lastName, yandexID, string(profileJSON), now, now)
	if err != nil {
		log.Printf("Failed to save user profile: %v", err)
	}
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}
