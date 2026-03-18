package main

import (
	"log"

	"bionicpro-auth/internal/app"
	"bionicpro-auth/internal/config"
)

func main() {
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("load config: %v", err)
	}

	a, err := app.New(cfg)
	if err != nil {
		log.Fatalf("init app: %v", err)
	}

	log.Printf("bionicpro-auth listening on %s", cfg.HTTPAddr)
	if err := a.Run(); err != nil {
		log.Fatalf("run app: %v", err)
	}
}
