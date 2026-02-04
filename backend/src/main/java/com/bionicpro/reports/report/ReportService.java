package com.bionicpro.reports.report;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Optional;

/**
 * Сервис отчётов. Читает подготовленные данные из OLAP-витрины без вычислений в реальном времени.
 */
@Service
public class ReportService {

    private final ReportRepository reportRepository;

    public ReportService(ReportRepository reportRepository) {
        this.reportRepository = reportRepository;
    }

    @Transactional(readOnly = true)
    public Optional<ReportResponse> getReportByUserId(String userId) {
        return reportRepository.findByUserId(userId)
                .map(ReportResponse::from);
    }
}
