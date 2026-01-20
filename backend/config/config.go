package config

import (
	"github.com/caarlos0/env/v6"
)

type Config struct {
	Issuer         string `env:"ISSUER"`
	ServerAddress  string `env:"SERVER_ADDRESS" envDefault:":8000"`
	AllowedOrigins string `env:"ALLOWED_ORIGINS" envDefault:"*"`
}

func Load() (*Config, error) {
	cfg := &Config{}
	err := env.Parse(cfg)
	if err != nil {
		return nil, err
	}
	return cfg, nil
}
