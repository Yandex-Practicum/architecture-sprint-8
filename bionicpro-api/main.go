package main

import (
	"context"
	"database/sql"
	"fmt"
	"log"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/coreos/go-oidc/v3/oidc"
	"github.com/jung-kurt/gofpdf"

	_ "github.com/ClickHouse/clickhouse-go/v2"
)

var verifier *oidc.IDTokenVerifier
var clickhouseDB *sql.DB

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

	clickhouseDB, err = sql.Open("clickhouse", "clickhouse://admin:admin@clickhouse:9000/bionicpro")
	if err != nil {
		log.Fatalf("Failed to connect to ClickHouse: %v", err)
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

	row := clickhouseDB.QueryRow(`
        SELECT latest_status, latest_battery_level, total_motor_cycles 
        FROM user_reports_datamart 
        WHERE username = ?
        ORDER BY report_generated_at DESC LIMIT 1`,
		claims.PreferredUsername,
	)

	var status string
	var battery, cycles int
	err = row.Scan(&status, &battery, &cycles)

	if err != nil {
		if err == sql.ErrNoRows {
			http.Error(w, "Данные для вашего отчета еще не сформированы", http.StatusNotFound)
			return
		}
		log.Printf("DB error: %v", err)
		http.Error(w, "Ошибка при получении данных", http.StatusInternalServerError)
		return
	}

	pdf := gofpdf.New("P", "mm", "A4", "")
	pdf.AddPage()

	pdf.SetFont("Arial", "B", 18)
	pdf.Cell(40, 10, "BionicPRO - Usage Report")
	pdf.Ln(15)

	pdf.SetFont("Arial", "", 12)
	pdf.Cell(40, 10, fmt.Sprintf("User: %s", claims.PreferredUsername))
	pdf.Ln(8)
	pdf.Cell(40, 10, fmt.Sprintf("Generated: %s", time.Now().Format("2006-01-02 15:04:05")))
	pdf.Ln(15)

	pdf.SetFont("Arial", "B", 14)
	pdf.Cell(40, 10, "Telemetry Data:")
	pdf.Ln(10)
	pdf.SetFont("Arial", "", 12)
	pdf.Cell(40, 8, fmt.Sprintf("- Status: %s", status))
	pdf.Ln(8)
	pdf.Cell(40, 8, fmt.Sprintf("- Battery Level: %d%%", battery))
	pdf.Ln(8)
	pdf.Cell(40, 8, fmt.Sprintf("- Motor Cycles: %d", cycles))
	pdf.Ln(15)
	pdf.Ln(8)
	pdf.Cell(40, 8, "- Firmware Version: v2.4.1")

	w.Header().Set("Content-Type", "application/pdf")
	w.Header().Set("Content-Disposition", `attachment; filename="bionic_report.pdf"`)

	if err := pdf.Output(w); err != nil {
		log.Printf("Failed to output PDF: %v", err)
		http.Error(w, "Failed to generate report", http.StatusInternalServerError)
	}
}
