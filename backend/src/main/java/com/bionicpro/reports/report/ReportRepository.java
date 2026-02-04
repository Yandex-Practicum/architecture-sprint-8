package com.bionicpro.reports.report;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

/**
 * Чтение из витрины отчётности (OLAP). Запись выполняется только ETL (Airflow).
 */
public interface ReportRepository extends JpaRepository<ReportDatamart, String> {

    Optional<ReportDatamart> findByUserId(String userId);
}
