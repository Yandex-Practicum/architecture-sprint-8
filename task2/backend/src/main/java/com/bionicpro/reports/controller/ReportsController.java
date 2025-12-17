package com.bionicpro.reports.controller;

import com.bionicpro.reports.dto.ReportResponse;
import com.bionicpro.reports.security.JwtAuthenticationFilter;
import com.bionicpro.reports.service.ReportsService;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.util.List;

@RestController
@RequestMapping("/api/reports")
public class ReportsController {

    private final ReportsService reportsService;

    public ReportsController(ReportsService reportsService) {
        this.reportsService = reportsService;
    }

    /**
     * Получить отчёт по текущему пользователю
     * GET /api/reports
     */
    @GetMapping
    public ResponseEntity<List<ReportResponse>> getReports(
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate startDate,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate endDate,
            Authentication authentication) {
        
        JwtAuthenticationFilter.UserInfo userInfo = (JwtAuthenticationFilter.UserInfo) authentication.getPrincipal();
        Long userId = userInfo.getUserId();
        
        // Пользователь может запрашивать только свои отчёты
        List<ReportResponse> reports = reportsService.getReportsByUserId(
            userId, 
            startDate, 
            endDate
        );
        
        return ResponseEntity.ok(reports);
    }

    /**
     * Получить отчёт по конкретному пользователю (только свои данные)
     * GET /api/reports/{userId}
     */
    @GetMapping("/{userId}")
    public ResponseEntity<List<ReportResponse>> getReportsByUserId(
            @PathVariable Long userId,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate startDate,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate endDate,
            Authentication authentication) {
        
        JwtAuthenticationFilter.UserInfo currentUser = (JwtAuthenticationFilter.UserInfo) authentication.getPrincipal();
        Long currentUserId = currentUser.getUserId();
        
        // Проверка: пользователь может запрашивать только свои отчёты
        if (!userId.equals(currentUserId)) {
            return ResponseEntity.status(403).build();
        }
        
        List<ReportResponse> reports = reportsService.getReportsByUserId(
            userId, 
            startDate, 
            endDate
        );
        
        return ResponseEntity.ok(reports);
    }
}

