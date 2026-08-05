package com.bionicpro.reports.web;

import com.bionicpro.reports.service.ReportOrchestrationService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.security.Principal;

@RestController
public class ReportsController {

    private final ReportOrchestrationService orchestrationService;

    public ReportsController(ReportOrchestrationService orchestrationService) {
        this.orchestrationService = orchestrationService;
    }

    @GetMapping("/reports")
    public ResponseEntity<?> getReport(Principal principal) {
        return orchestrationService.resolveReportUrl(principal.getName())
                .<ResponseEntity<?>>map(url -> ResponseEntity.ok(new ReportUrlResponse(url)))
                .orElseGet(() -> ResponseEntity.status(404)
                        .body(new ErrorResponse("No processed reporting period is available for this user yet")));
    }

    private record ReportUrlResponse(String reportUrl) {
    }

    private record ErrorResponse(String message) {
    }
}
