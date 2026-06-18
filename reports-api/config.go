package main

import (
	"os"
	"strconv"
	"time"
)

type config struct {
	Listen string
	Env    string

	ClickhouseHost     string
	ClickhousePort     int
	ClickhouseUser     string
	ClickhousePassword string
	ClickhouseDB       string

	QueryTimeout time.Duration
}

func loadConfig() config {
	return config{
		Listen:            getenv("LISTEN", ":8000"),
		Env:               getenv("APP_ENV", "dev"),
		ClickhouseHost:    getenv("CLICKHOUSE_HOST", "clickhouse"),
		ClickhousePort:    getenvInt("CLICKHOUSE_PORT", 8123),
		ClickhouseUser:    getenv("CLICKHOUSE_USER", "default"),
		ClickhousePassword: getenv("CLICKHOUSE_PASSWORD", ""),
		ClickhouseDB:      getenv("CLICKHOUSE_DB", "bionicpro_dm"),
		QueryTimeout:      10 * time.Second,
	}
}

func getenv(k, def string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return def
}

func getenvInt(k string, def int) int {
	if v := os.Getenv(k); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			return n
		}
	}
	return def
}