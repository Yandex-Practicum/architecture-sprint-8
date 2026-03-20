package main

import (
	"log"

	"reports-api/internal/app"
	"reports-api/internal/config"
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

	log.Printf("reports-api listening on %s", cfg.HTTPAddr)
	if err := a.Run(); err != nil {
		log.Fatalf("run app: %v", err)
	}
}
