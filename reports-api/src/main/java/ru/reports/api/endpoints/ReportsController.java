package ru.reports.api.endpoints;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import ru.reports.api.response.ProstheticReportResponse;
import ru.reports.api.service.ReportService;

import java.time.LocalDate;
import java.util.List;

@RestController
@RequestMapping("/reports")
@Tag(name = "Reports", description = "Отчёты по работе бионического протеза")
public class ReportsController {

    private  final ReportService reportService;

    public ReportsController(ReportService reportService) {
        this.reportService = reportService;
    }

    @GetMapping
    @Operation(
            summary = "Получить отчёт текущего пользователя за период",
            security = @SecurityRequirement(name = "keycloak-oauth2")
    )
    public List<ProstheticReportResponse> getMyReports(
            JwtAuthenticationToken authentication,
            @RequestParam LocalDate from,
            @RequestParam LocalDate to
    ) {
        String userId = authentication.getToken().getClaimAsString("preferred_username");

        return reportService.getReportsForUser(userId, from, to);
    }
}
