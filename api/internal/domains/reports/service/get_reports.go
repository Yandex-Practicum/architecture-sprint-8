package service

import (
	"time"

	"github.com/nini-k/architecture-sprint-8/api/internal/domains/reports/entities"
)

func (s *service) GetReports() ([]entities.Report, error) {
	return []entities.Report{
		{Id: 1, Name: "Финансовый отчет", CreatedAt: time.Now()},
		{Id: 2, Name: "Какой-то отчет", CreatedAt: time.Now()},
		{Id: 3, Name: "Отчет по аналитике данных", CreatedAt: time.Now()},
	}, nil
}
