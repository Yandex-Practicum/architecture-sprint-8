package com.bionicpro.reports.report;

import com.bionicpro.reports.security.CurrentUser;
import org.springframework.http.ResponseEntity;

import org.springframework.web.bind.annotation.*;

import java.util.Optional;

/**
 * API отчётов. Доступ к отчёту предоставляется только в отношении себя (текущего пользователя).
 */
@RestController
@RequestMapping("/api/reports")
public class ReportsController {

    private final ReportService reportService;

    public ReportsController(ReportService reportService) {
        this.reportService = reportService;
    }

    /**
     * Получить отчёт текущего пользователя (без указания userId в пути).
     * Удобно для клиента: не нужно знать свой идентификатор.
     */
    @GetMapping("/me")
    public ResponseEntity<ReportResponse> getMyReport() {
        return CurrentUser.getUserId()
                .flatMap(reportService::getReportByUserId)
                .map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }

    /**
     * Получить отчёт по указанному пользователю.
     * Доступ разрешён только если запрашиваемый userId совпадает с текущим аутентифицированным пользователем.
     * Иначе — 403 Forbidden.
     *
     * @param userId идентификатор пользователя (должен совпадать с текущим пользователем)
     */
    @GetMapping("/user/{userId}")
    public ResponseEntity<ReportResponse> getReportByUser(@PathVariable String userId) {
        Optional<String> currentUserId = CurrentUser.getUserId();
        if (currentUserId.isEmpty()) {
            return ResponseEntity.status(401).build();
        }
        if (!currentUserId.get().equals(userId)) {
            return ResponseEntity.status(403).build();
        }
        return reportService.getReportByUserId(userId)
                .map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }
}
