package com.bionicpro.reports.report;

import com.fasterxml.jackson.annotation.JsonInclude;

import java.time.Instant;
import java.time.LocalDate;

/**
 * DTO отчёта по пользователю для API. Данные из витрины OLAP без вычислений в реальном времени.
 */
@JsonInclude(JsonInclude.Include.NON_NULL)
public class ReportResponse {

    private String userId;
    private String deviceId;
    private String customerName;
    private String customerEmail;
    private LocalDate contractDate;
    private String prosthesisModel;
    private LocalDate deliveryDate;
    private int sessionCount;
    private long totalUsageSeconds;
    private Long totalUsageMinutes;  // производное для удобства клиента
    private int eventCount;
    private int errorCount;
    private int calibrationCount;
    private Instant periodStart;
    private Instant periodEnd;
    private Instant lastActivityUtc;
    private Instant updatedAt;

    public static ReportResponse from(ReportDatamart entity) {
        ReportResponse r = new ReportResponse();
        r.setUserId(entity.getUserId());
        r.setDeviceId(entity.getDeviceId());
        r.setCustomerName(entity.getCustomerName());
        r.setCustomerEmail(entity.getCustomerEmail());
        r.setContractDate(entity.getContractDate());
        r.setProsthesisModel(entity.getProsthesisModel());
        r.setDeliveryDate(entity.getDeliveryDate());
        r.setSessionCount(entity.getSessionCount());
        r.setTotalUsageSeconds(entity.getTotalUsageSeconds());
        r.setTotalUsageMinutes(entity.getTotalUsageSeconds() / 60);
        r.setEventCount(entity.getEventCount());
        r.setErrorCount(entity.getErrorCount());
        r.setCalibrationCount(entity.getCalibrationCount());
        r.setPeriodStart(entity.getPeriodStart());
        r.setPeriodEnd(entity.getPeriodEnd());
        r.setLastActivityUtc(entity.getLastActivityUtc());
        r.setUpdatedAt(entity.getUpdatedAt());
        return r;
    }

    public String getUserId() {
        return userId;
    }

    public void setUserId(String userId) {
        this.userId = userId;
    }

    public String getDeviceId() {
        return deviceId;
    }

    public void setDeviceId(String deviceId) {
        this.deviceId = deviceId;
    }

    public String getCustomerName() {
        return customerName;
    }

    public void setCustomerName(String customerName) {
        this.customerName = customerName;
    }

    public String getCustomerEmail() {
        return customerEmail;
    }

    public void setCustomerEmail(String customerEmail) {
        this.customerEmail = customerEmail;
    }

    public LocalDate getContractDate() {
        return contractDate;
    }

    public void setContractDate(LocalDate contractDate) {
        this.contractDate = contractDate;
    }

    public String getProsthesisModel() {
        return prosthesisModel;
    }

    public void setProsthesisModel(String prosthesisModel) {
        this.prosthesisModel = prosthesisModel;
    }

    public LocalDate getDeliveryDate() {
        return deliveryDate;
    }

    public void setDeliveryDate(LocalDate deliveryDate) {
        this.deliveryDate = deliveryDate;
    }

    public int getSessionCount() {
        return sessionCount;
    }

    public void setSessionCount(int sessionCount) {
        this.sessionCount = sessionCount;
    }

    public long getTotalUsageSeconds() {
        return totalUsageSeconds;
    }

    public void setTotalUsageSeconds(long totalUsageSeconds) {
        this.totalUsageSeconds = totalUsageSeconds;
    }

    public Long getTotalUsageMinutes() {
        return totalUsageMinutes;
    }

    public void setTotalUsageMinutes(Long totalUsageMinutes) {
        this.totalUsageMinutes = totalUsageMinutes;
    }

    public int getEventCount() {
        return eventCount;
    }

    public void setEventCount(int eventCount) {
        this.eventCount = eventCount;
    }

    public int getErrorCount() {
        return errorCount;
    }

    public void setErrorCount(int errorCount) {
        this.errorCount = errorCount;
    }

    public int getCalibrationCount() {
        return calibrationCount;
    }

    public void setCalibrationCount(int calibrationCount) {
        this.calibrationCount = calibrationCount;
    }

    public Instant getPeriodStart() {
        return periodStart;
    }

    public void setPeriodStart(Instant periodStart) {
        this.periodStart = periodStart;
    }

    public Instant getPeriodEnd() {
        return periodEnd;
    }

    public void setPeriodEnd(Instant periodEnd) {
        this.periodEnd = periodEnd;
    }

    public Instant getLastActivityUtc() {
        return lastActivityUtc;
    }

    public void setLastActivityUtc(Instant lastActivityUtc) {
        this.lastActivityUtc = lastActivityUtc;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }

    public void setUpdatedAt(Instant updatedAt) {
        this.updatedAt = updatedAt;
    }
}
