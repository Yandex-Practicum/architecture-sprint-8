package ru.reports.api.exceptions;

public class ReportNotAvailableException extends RuntimeException {

    public ReportNotAvailableException(String message) {
        super(message);
    }
}
