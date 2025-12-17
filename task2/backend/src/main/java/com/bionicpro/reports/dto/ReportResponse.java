package com.bionicpro.reports.dto;

import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDate;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class ReportResponse {
    private Long userId;
    private String email;
    private String firstName;
    private String lastName;
    private String prosthesisId;
    
    @JsonFormat(pattern = "yyyy-MM-dd")
    private LocalDate reportDate;
    
    private Integer totalActions;
    private Double avgResponseTime;
    private Double maxResponseTime;
    private Double minResponseTime;
    
    private Integer graspCount;
    private Integer releaseCount;
    private Integer flexCount;
    
    private Double avgBatteryLevel;
    private Double minBatteryLevel;
    
    private Integer totalUsageSeconds;
    private Double usageHours;
    private Double actionsPerHour;
    private Double efficiencyScore;
    
    @JsonFormat(pattern = "yyyy-MM-dd")
    private LocalDate orderDate;
    
    private String status;
}

