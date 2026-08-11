package com.bionicpro.reports.service;

public record CustomerMartRow(
        String username,
        String firstName,
        String lastName,
        String prostheticId,
        String country,
        String periodStart,
        String periodEnd,
        int eventsCount,
        double avgLatencyMs,
        double avgSignalQuality) {
}
