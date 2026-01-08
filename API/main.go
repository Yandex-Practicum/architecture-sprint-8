package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gin-contrib/cors"
	"github.com/gin-gonic/gin"
	"github.com/spf13/viper"
	"github.com/tbaehler/gin-keycloak/pkg/ginkeycloak"
)

const (
	CFG_PORT                    = "port"
	CFG_PORT_DEFAULT            = "8090"
	CFG_KEYCLOAK_URL            = "keycloak_url"
	CFG_KEYCLOAK_URL_DEFAULT    = "http://keycloak:8080"
	CFG_KEYCLOAK_REALM          = "keycloak_realm"
	CFG_KEYCLOAK_REALM_DEFAULT  = "reports-realm"
	CFG_KEYCLOAK_CLIENT         = "keycloak_client"
	CFG_KEYCLOAK_CLIENT_DEFAULT = "reports-api"
	CFG_ALLOW_ROLE              = "allow_role"
	CFG_ALLOW_ROLE_DEFAULT      = "prothetic_user"
)

func main() {

	// Prepare config
	viper.SetDefault(CFG_PORT, CFG_PORT_DEFAULT)
	viper.SetDefault(CFG_KEYCLOAK_URL, CFG_KEYCLOAK_URL_DEFAULT)
	viper.SetDefault(CFG_KEYCLOAK_REALM, CFG_KEYCLOAK_REALM_DEFAULT)
	viper.SetDefault(CFG_KEYCLOAK_CLIENT, CFG_KEYCLOAK_CLIENT_DEFAULT)
	viper.SetDefault(CFG_ALLOW_ROLE, CFG_ALLOW_ROLE_DEFAULT)
	viper.AutomaticEnv()

	// Prepare router
	router := gin.Default()
	router.Use(ginkeycloak.RequestLogger([]string{"uid"}, "data"))
	router.Use(gin.Recovery())

  headers := []string{"Content-Type", "Content-Length", "Accept-Encoding", "X-CSRF-Token", "Authorization", "accept", "origin", "Cache-Control", "X-Requested-With", "Token"}

	cfg := cors.DefaultConfig()
	cfg.AllowAllOrigins = true
	cfg.AllowCredentials = true
	cfg.AllowHeaders = append(cfg.AllowHeaders, headers...)
	router.Use(cors.New(cfg))

	// Prepare keycloack
	keycloackConfig := ginkeycloak.BuilderConfig{
		Url:   viper.GetString(CFG_KEYCLOAK_URL),
		Realm: viper.GetString(CFG_KEYCLOAK_REALM),
	}

	// Add private api
	privateApi := router.Group("/reports")
	privateApi.Use(
		ginkeycloak.NewAccessBuilder(keycloackConfig).
			RestrictButForRealm(viper.GetString(CFG_ALLOW_ROLE)).Build(),
	)
	privateApi.GET("/", func(ctx *gin.Context) {
		ctx.JSON(http.StatusOK, "ok")
	})

	// Prepare server
	srv := &http.Server{
		Addr:    fmt.Sprintf(":%v", viper.GetInt(CFG_PORT)),
		Handler: router.Handler(),
	}

	go func() {
		// service connections
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("listen: %s\n", err)
		}
	}()

	// Wait for interrupt signal to gracefully shutdown the server with
	// a timeout of 5 seconds.
	quit := make(chan os.Signal, 1)
	// kill (no param) default send syscall.SIGTERM
	// kill -2 is syscall.SIGINT
	// kill -9 is syscall. SIGKILL but can"t be catch, so don't need add it
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit
	log.Println("Shutdown Server ...")

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := srv.Shutdown(ctx); err != nil {
		log.Fatal("Server Shutdown:", err)
	}
	// catching ctx.Done(). timeout of 5 seconds.
	select {
	case <-ctx.Done():
		log.Println("timeout of 5 seconds.")
	}
	log.Println("Server exiting")
}
