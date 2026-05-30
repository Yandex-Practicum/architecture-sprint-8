package ru.bionicpro.reports.model;

import lombok.Data;

import java.time.LocalDate;
import java.time.LocalDateTime;

@Data
public class UserReport {

    private String userId;

    private String userName;
    private String email;
    private String phone;
    private String prosthesisModel;
    private String serialNumber;
    private LocalDate registrationDate;

    private Integer totalMovements;
    private Double avgReactionTime;
    private Double medianReactionTime;
    private Integer minReactionTime;
    private Integer maxReactionTime;
    private Double avgSignalQuality;
    private Double minSignalQuality;
    private Integer avgBatteryLevel;

    private Double performanceScore;
    private Boolean needsCalibration;

    private LocalDate lastActiveDate;
    private LocalDateTime updatedAt;
}