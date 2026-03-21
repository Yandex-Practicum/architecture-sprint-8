package config

import (
	"net/http"
	"strings"
	"time"

	env "github.com/caarlos0/env/v11"
)

type Config struct {
	HTTPAddr           string        `env:"HTTP_ADDR" envDefault:":8082"`
	SessionCookieName  string        `env:"SESSION_COOKIE_NAME" envDefault:"bionicpro_session"`
	AuthServiceURL     string        `env:"AUTH_SERVICE_URL,required"`
	ClickHouseAddr     string        `env:"CLICKHOUSE_ADDR" envDefault:"clickhouse:9000"`
	ClickHouseUser     string        `env:"CLICKHOUSE_USER" envDefault:"ch_user"`
	ClickHousePassword string        `env:"CLICKHOUSE_PASSWORD" envDefault:"ch_pass"`
	ClickHouseDatabase string        `env:"CLICKHOUSE_DATABASE" envDefault:"reports"`
	RequestTimeout     time.Duration `env:"REQUEST_TIMEOUT" envDefault:"5s"`
	AllowedOrigins     []string      `env:"ALLOWED_ORIGINS" envSeparator:","`
	S3Endpoint         string        `env:"S3_ENDPOINT" envDefault:"minio:9090"`
	S3AccessKey        string        `env:"S3_ACCESS_KEY" envDefault:"minioadmin"`
	S3SecretKey        string        `env:"S3_SECRET_KEY" envDefault:"minioadmin"`
	S3Bucket           string        `env:"S3_BUCKET" envDefault:"static"`
	CDNBaseURL         string        `env:"CDN_BASE_URL" envDefault:"http://localhost:8085"`
}

func Load() (Config, error) {
	var cfg Config
	if err := env.Parse(&cfg); err != nil {
		return Config{}, err
	}
	if len(cfg.AllowedOrigins) == 0 {
		cfg.AllowedOrigins = []string{}
	}
	return cfg, nil
}

func (c Config) SameSite() http.SameSite {
	return http.SameSiteLaxMode
}

func (c Config) AllowedOrigin(origin string) bool {
	for _, o := range c.AllowedOrigins {
		if strings.EqualFold(strings.TrimSpace(o), origin) {
			return true
		}
	}
	return false
}
