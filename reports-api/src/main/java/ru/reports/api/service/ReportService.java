package ru.reports.api.service;

import org.springframework.stereotype.Service;
import ru.reports.api.repository.ReportRepository;
import ru.reports.api.response.ProstheticReportResponse;

import java.time.LocalDate;
import java.util.List;

@Service
public class ReportService {

    private final ReportRepository reportRepository;

    public ReportService(ReportRepository reportRepository) {
        this.reportRepository = reportRepository;
    }

    public List<ProstheticReportResponse> getReportsForUser(
            String userId,
            LocalDate from,
            LocalDate to
    ) {
        if (from.isAfter(to)) {
            throw new IllegalArgumentException("Дата начала периода не может быть позже даты окончания");
        }

        return reportRepository.findByUserIdAndPeriod(userId, from, to);
    }
}
