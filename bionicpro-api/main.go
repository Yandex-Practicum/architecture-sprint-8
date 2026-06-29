package main

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"github.com/minio/minio-go/v7/pkg/credentials"
	"log"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/coreos/go-oidc/v3/oidc"
	"github.com/jung-kurt/gofpdf"
	"github.com/minio/minio-go/v7"

	_ "github.com/ClickHouse/clickhouse-go/v2"
)

var verifier *oidc.IDTokenVerifier
var clickhouseDB *sql.DB
var minioClient *minio.Client

func init() {
	keycloakURL := os.Getenv("KEYCLOAK_URL")
	if keycloakURL == "" {
		keycloakURL = "http://keycloak:8080/realms/reports-realm"
	}

	ctx := context.Background()
	provider, err := oidc.NewProvider(ctx, keycloakURL)
	if err != nil {
		log.Fatalf("Failed to initialize OIDC provider: %v", err)
	}

	oidcConfig := &oidc.Config{
		SkipClientIDCheck: true,
		SkipIssuerCheck:   true,
	}
	verifier = provider.Verifier(oidcConfig)

	// Allow overriding ClickHouse DSN via env; default points to new CDC-based schema
	chDSN := os.Getenv("CLICKHOUSE_DSN")
	if chDSN == "" {
		chDSN = "clickhouse://admin:admin@clickhouse:9000/crm_dds"
	}
	clickhouseDB, err = sql.Open("clickhouse", chDSN)
	if err != nil {
		log.Fatalf("Failed to connect to ClickHouse: %v", err)
	}

	minioClient, err = minio.New("minio:9000", &minio.Options{
		Creds:  credentials.NewStaticV4("minioadmin", "minioadmin", ""),
		Secure: false,
	})
	if err != nil {
		log.Fatalf("Failed to connect to MinIO S3: %v", err)
	}
}

func main() {
	http.HandleFunc("/api/report", reportHandler)

	log.Println("BionicPRO API Server is running on port 8000...")
	log.Fatal(http.ListenAndServe(":8000", nil))
}

func reportHandler(w http.ResponseWriter, r *http.Request) {
	authHeader := r.Header.Get("Authorization")
	if !strings.HasPrefix(authHeader, "Bearer ") {
		http.Error(w, "Unauthorized: No token provided", http.StatusUnauthorized)
		return
	}

	rawToken := strings.TrimPrefix(authHeader, "Bearer ")

	token, err := verifier.Verify(r.Context(), rawToken)
	if err != nil {
		http.Error(w, "Unauthorized: Invalid token", http.StatusUnauthorized)
		return
	}

	var claims struct {
		PreferredUsername string `json:"preferred_username"`
		RealmAccess       struct {
			Roles []string `json:"roles"`
		} `json:"realm_access"`
	}
	if err := token.Claims(&claims); err != nil {
		http.Error(w, "Internal Error: Failed to parse token claims", http.StatusInternalServerError)
		return
	}

	hasRole := false
	for _, role := range claims.RealmAccess.Roles {
		if role == "prothetic_user" {
			hasRole = true
			break
		}
	}

	if !hasRole {
		http.Error(w, "Forbidden: You don't have permission to download reports", http.StatusForbidden)
		return
	}

	log.Printf("User %s requested a report", claims.PreferredUsername)

	username := claims.PreferredUsername

	bucketName := "bionicpro-reports"
	currentDate := time.Now().Format("20060102")
	objectName := fmt.Sprintf("reports/%s/report_%s.pdf", username, currentDate)
	cdnURL := fmt.Sprintf("http://localhost:8086/%s", objectName)

	ctx := context.Background()

	_, err = minioClient.StatObject(ctx, bucketName, objectName, minio.StatObjectOptions{})
	if err == nil {
		log.Printf("Report for %s found in S3 cache. Returning CDN link.", username)
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{"url": cdnURL})
		return
	}

	log.Printf("Report for %s not found in S3. Generating fresh report...", username)
	row := clickhouseDB.QueryRow(`
		SELECT username, email, full_name
		FROM crm_dds.crm_users FINAL
		WHERE username = ?
		ORDER BY user_id ASC
		LIMIT 1`,
		username,
	)

	var chUsername, chEmail string
	var chFullName sql.NullString
	if err := row.Scan(&chUsername, &chEmail, &chFullName); err != nil {
		if err == sql.ErrNoRows {
			http.Error(w, "Профиль пользователя не найден в витрине CRM", http.StatusNotFound)
			return
		}
		log.Printf("DB error: %v", err)
		http.Error(w, "Ошибка при получении данных", http.StatusInternalServerError)
		return
	}

	fullName := chFullName.String
	if !chFullName.Valid || strings.TrimSpace(fullName) == "" {
		fullName = "N/A"
	}

	pdf := gofpdf.New("P", "mm", "A4", "")
	pdf.AddPage()

	pdf.SetFont("Arial", "B", 18)
	pdf.Cell(40, 10, "BionicPRO - CRM User Report")
	pdf.Ln(15)

	pdf.SetFont("Arial", "", 12)
	pdf.Cell(40, 10, fmt.Sprintf("User: %s", claims.PreferredUsername))
	pdf.Ln(8)
	pdf.Cell(40, 10, fmt.Sprintf("Generated: %s", time.Now().Format("2006-01-02 15:04:05")))
	pdf.Ln(15)

	pdf.SetFont("Arial", "B", 14)
	pdf.Cell(40, 10, "CRM Profile:")
	pdf.Ln(10)
	pdf.SetFont("Arial", "", 12)
	pdf.Cell(40, 8, fmt.Sprintf("- Username: %s", chUsername))
	pdf.Ln(8)
	pdf.Cell(40, 8, fmt.Sprintf("- Email: %s", chEmail))
	pdf.Ln(8)
	pdf.Cell(40, 8, fmt.Sprintf("- Full name: %s", fullName))
	pdf.Ln(15)

	var pdfBuffer bytes.Buffer
	if err := pdf.Output(&pdfBuffer); err != nil {
		http.Error(w, "Failed to build PDF", http.StatusInternalServerError)
		return
	}

	_, err = minioClient.PutObject(ctx, bucketName, objectName, &pdfBuffer, int64(pdfBuffer.Len()), minio.PutObjectOptions{
		ContentType: "application/pdf",
	})
	if err != nil {
		log.Printf("S3 Upload Error: %v", err)
		http.Error(w, "Failed to save report to S3", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"url": cdnURL})
}
