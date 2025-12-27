package main

import (
	"context"
	"fmt"
	"log"
	"os"

	"github.com/lestrrat-go/jwx/jwk"
	reports "github.com/nini-k/architecture-sprint-8/api/internal/domains/reports/service"
	"github.com/nini-k/architecture-sprint-8/api/internal/transport/http"
)

const (
	appAddrEnv       = "API_APP_ADDR"
	keycloakAddrEnv  = "API_KEYCLOAK_ADDR"
	keycloakRealmEnv = "API_KEYCLOAK_REALM"
)

func main() {
	addr := os.Getenv(appAddrEnv)
	if addr == "" {
		log.Fatalf("%s must be not empty value", appAddrEnv)
	}

	keycloakAddr := os.Getenv(keycloakAddrEnv)
	if keycloakAddr == "" {
		log.Fatalf("%s must be not empty value", keycloakAddrEnv)
	}

	keycloakRealm := os.Getenv(keycloakRealmEnv)
	if keycloakRealm == "" {
		log.Fatalf("%s must be not empty value", keycloakRealmEnv)
	}

	ctx := context.Background()

	jwkURL := fmt.Sprintf("%s/realms/%s/protocol/openid-connect/certs", keycloakAddr, keycloakRealm)
	set, err := jwk.Fetch(ctx, jwkURL)
	if err != nil {
		log.Fatalf("jwk.Fetch: %s", err.Error())
	}

	r := http.NewEngine(
		set,
		reports.New(),
	)

	r.Run(addr)
}
