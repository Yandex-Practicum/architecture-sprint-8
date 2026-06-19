package ru.reports.api.service;

import org.springframework.stereotype.Service;
import ru.reports.api.exceptions.ReportNotAvailableException;
import ru.reports.api.repository.ReportRepository;
import ru.reports.api.response.ProstheticReportResponse;

import java.time.LocalDate;
import java.util.List;

@Service
public class ReportService {

    private final ReportRepository repository;

    public ReportService(ReportRepository repository) {
        this.repository = repository;
    }

    public List<ProstheticReportResponse> getReportsForUser(
            String userId,
            LocalDate from,
            LocalDate to
    ) {
        if (from.isAfter(to)) {
            throw new IllegalArgumentException("Дата начала периода не может быть позже даты окончания");
        }

        LocalDate maxProcessedDate = repository.findMaxProcessedDateByUserId(userId)
                .orElseThrow(() -> new ReportNotAvailableException(
                        "Для пользователя ещё нет обработанных отчётов"
                ));

        if (to.isAfter(maxProcessedDate)) {
            throw new ReportNotAvailableException(
                    "Запрошенный период ещё не обработан Airflow. Последняя доступная дата: " + maxProcessedDate
            );
        }

        return repository.findByUserIdAndPeriod(userId, from, to);
    }
}
