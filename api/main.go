package main

import (
	"github.com/gin-contrib/cors"
	"github.com/gin-gonic/gin"
	"github.com/tbaehler/gin-keycloak/pkg/ginkeycloak"
	"os"
)

var (
	keycloakUrl             = os.Getenv("KEYCLOAK_URL")
	keycloakRealm           = os.Getenv("KEYCLOAK_REALM")
	keycloakAllowedUserRole = os.Getenv("KEYCLOAK_ALLOWED_USER_ROLE")
)

func main() {
	router := gin.Default()

	config := initCorsConfig()

	router.Use(cors.New(config))
	router.Use(ginkeycloak.RequestLogger([]string{"uid"}, "data"))

	keycloakConfig := ginkeycloak.BuilderConfig{
		Url:   keycloakUrl,
		Realm: keycloakRealm,
	}

	router.Use(
		ginkeycloak.
			NewAccessBuilder(keycloakConfig).
			RestrictButForRealm(keycloakAllowedUserRole).
			Build(),
	)

	router.GET("/reports", func(context *gin.Context) {
		context.JSON(200, gin.H{
			"message": "hello",
		})
	})

	// Start server
	err := router.Run(":8000")
	if err != nil {

	}
}

func initCorsConfig() cors.Config {
	config := cors.DefaultConfig()
	config.AllowAllOrigins = true
	config.AllowCredentials = true
	config.AllowMethods = []string{"POST", "GET", "PUT", "OPTIONS"}
	config.AllowHeaders = []string{"Origin", "Content-Type", "Authorization", "Accept", "User-Agent", "Cache-Control", "Pragma"}
	config.ExposeHeaders = []string{"Content-Length"}
	return config
}
