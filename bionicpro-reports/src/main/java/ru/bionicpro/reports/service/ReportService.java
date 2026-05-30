package ru.bionicpro.reports.service;

import ru.bionicpro.reports.model.ReportResponse;

public interface ReportService {
    ReportResponse getReportWithUrl(String userId, String format);

    String exportReportToXml(String userId);

}