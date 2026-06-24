package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/coreos/go-oidc/v3/oidc"
	"github.com/jung-kurt/gofpdf"
)

var verifier *oidc.IDTokenVerifier

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
	pdf.Cell(40, 8, "- Status: Active")
	pdf.Ln(8)
	pdf.Cell(40, 8, "- Battery Level: 87%")
	pdf.Ln(8)
	pdf.Cell(40, 8, "- Motor Cycles: 12,450")
	pdf.Ln(8)
	pdf.Cell(40, 8, "- Firmware Version: v2.4.1")

	w.Header().Set("Content-Type", "application/pdf")
	w.Header().Set("Content-Disposition", `attachment; filename="bionic_report.pdf"`)

	if err := pdf.Output(w); err != nil {
		log.Printf("Failed to output PDF: %v", err)
		http.Error(w, "Failed to generate report", http.StatusInternalServerError)
	}
}
