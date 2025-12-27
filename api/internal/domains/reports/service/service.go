package service

import "github.com/nini-k/architecture-sprint-8/api/internal/domains/reports/entities"

type Service interface {
	GetReports() ([]entities.Report, error)
}

type service struct {
}

func New() Service {
	return &service{}
}
