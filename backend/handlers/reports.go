package handlers

import (
	"encoding/json"
	"math/rand"
	"net/http"
	"time"
)

type Reading struct {
	Timestamp time.Time `json:"timestamp"`
	Sensor    string    `json:"sensor"`
	Value     float64   `json:"value"`
}

type Report struct {
	GeneratedAt time.Time `json:"generated_at"`
	Readings    []Reading `json:"readings"`
}

var sensors = []string{"EMG1", "EMG2", "IMU1", "IMU2", "Battery"}

func ReportsHandler(w http.ResponseWriter, _ *http.Request) {
	now := time.Now()
	readings := make([]Reading, len(sensors))
	for i, sensor := range sensors {
		readings[i] = Reading{
			Timestamp: now.Add(-time.Duration(rand.Intn(1000)) * time.Millisecond),
			Sensor:    sensor,
			Value:     rand.Float64() * 100,
		}
	}
	report := Report{
		GeneratedAt: now,
		Readings:    readings,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(report)
}
