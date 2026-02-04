package com.bionicpro.reports.report;

import jakarta.persistence.*;
import java.time.Instant;
import java.time.LocalDate;

/**
 * Сущность витрины отчётности (OLAP). Только чтение — заполняется ETL (Airflow).
 */
@Entity
@Table(name = "report_datamart")
public class ReportDatamart {

    @Id
    @Column(name = "user_id", length = 64, nullable = false)
    private String userId;

    @Column(name = "device_id", length = 64)
    private String deviceId;

    @Column(name = "customer_name", length = 255)
    private String customerName;

    @Column(name = "customer_email", length = 255)
    private String customerEmail;

    @Column(name = "contract_date")
    private LocalDate contractDate;

    @Column(name = "prosthesis_model", length = 128)
    private String prosthesisModel;

    @Column(name = "delivery_date")
    private LocalDate deliveryDate;

    @Column(name = "session_count", nullable = false)
    private int sessionCount = 0;

    @Column(name = "total_usage_seconds", nullable = false)
    private long totalUsageSeconds = 0;

    @Column(name = "event_count", nullable = false)
    private int eventCount = 0;

    @Column(name = "error_count", nullable = false)
    private int errorCount = 0;

    @Column(name = "calibration_count", nullable = false)
    private int calibrationCount = 0;

    @Column(name = "period_start")
    private Instant periodStart;

    @Column(name = "period_end")
    private Instant periodEnd;

    @Column(name = "last_activity_utc")
    private Instant lastActivityUtc;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

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
