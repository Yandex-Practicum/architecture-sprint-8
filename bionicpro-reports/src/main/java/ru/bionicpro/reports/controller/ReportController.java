package ru.bionicpro.reports.controller;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.*;
import ru.bionicpro.reports.model.ReportResponse;
import ru.bionicpro.reports.service.ReportService;

@Slf4j
@RestController
//@CrossOrigin(origins = "http://localhost:3000", allowCredentials = "true")
@RequestMapping("/api/reports")
@RequiredArgsConstructor
public class ReportController {

    private final ReportService reportService;

    @GetMapping(value = "/{userId}", produces = "application/json")
    @PreAuthorize("hasRole('REPORTS_USER') or #userId == authentication.principal.claim['sub']")
    public ResponseEntity<ReportResponse> getReportByUserId(
            @PathVariable String userId,
            @RequestParam(required = false, defaultValue = "xml") String format,
            @AuthenticationPrincipal Jwt jwt) {

        log.info("Request received - userId: {}, format: {}", userId, format);
        log.info("Token sub: {}, preferred_username: {}",
                jwt.getClaim("sub"), jwt.getClaim("preferred_username"));

        // Проверка, что пользователь запрашивает свой отчёт
        String tokenUserId = jwt.getClaim("sub");
        if (!tokenUserId.equals(userId)) {
            log.warn("Access denied: user {} tried to access report of {}", tokenUserId, userId);
            return ResponseEntity.status(403).build();
        }

        String username = jwt.getClaim("preferred_username");
        ReportResponse response = reportService.getReportWithUrl(username, format);

        return ResponseEntity.ok(response);
    }

}