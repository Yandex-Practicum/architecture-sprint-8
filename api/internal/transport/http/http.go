package http

import (
	"fmt"
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/lestrrat-go/jwx/jwk"
	reports "github.com/nini-k/architecture-sprint-8/api/internal/domains/reports/service"
)

func NewEngine(jwkSet jwk.Set, reportsSvc reports.Service) *gin.Engine {
	r := gin.Default()

	r.Use(func(c *gin.Context) {
		c.Writer.Header().Set("Access-Control-Allow-Origin", "*")
		c.Writer.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		c.Writer.Header().Set("Access-Control-Allow-Headers", "Origin, Content-Type, Authorization")
		c.Writer.Header().Set("Access-Control-Allow-Credentials", "true")

		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(204)
			return
		}

		c.Next()
	})

	r.Use(AuthMiddleware(jwkSet))

	r.GET("/reports", func(c *gin.Context) {
		rolesAny, ok := c.Get("roles")
		if !ok {
			c.JSON(http.StatusForbidden, ErrorMessage{Error: "roles not found"})
			return
		}

		roles, ok := rolesAny.([]interface{})
		if !ok {
			c.JSON(http.StatusInternalServerError, ErrorMessage{Error: "incorrect roles value"})
		}

		m := make(map[string]struct{}, len(roles))
		for _, role := range roles {
			v, ok := role.(string)
			if !ok {
				continue
			}

			m[v] = struct{}{}
		}

		if _, ok := m[protheticUserRoleName]; !ok {
			c.JSON(http.StatusForbidden, ErrorMessage{Error: "user is denied access to API"})
			return
		}

		reports, err := reportsSvc.GetReports()
		if err != nil {
			c.JSON(http.StatusInternalServerError, ErrorMessage{
				Error: fmt.Errorf("reportsSvc.GetReports: %w", err).Error(),
			})
		}

		c.JSON(http.StatusOK, reports)
	})

	return r
}
