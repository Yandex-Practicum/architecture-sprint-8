package ru.bionicpro.api;

import java.time.LocalDate;

public record ReportEntry(
        LocalDate reportDate,
        String prosthesisSerial,
        Long totalMovements,
        Double avgResponseMs,
        Double activeHours
) {
}
