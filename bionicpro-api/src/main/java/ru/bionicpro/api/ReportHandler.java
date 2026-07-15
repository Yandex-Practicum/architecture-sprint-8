package ru.bionicpro.api;

import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.server.ServerRequest;
import org.springframework.web.reactive.function.server.ServerResponse;
import reactor.core.publisher.Mono;
import tools.jackson.databind.ObjectMapper;

import java.security.Principal;
import java.time.LocalDate;

@Component
public final class ReportHandler {

    private final ReportService reportService;

    private final S3Service s3Service;

    private final CdnService cdnService;

    private final ObjectMapper objectMapper;

    public ReportHandler(
            ReportService reportService,
            S3Service s3Service,
            CdnService cdnService,
            ObjectMapper objectMapper
    ) {
        this.reportService = reportService;
        this.s3Service = s3Service;
        this.cdnService = cdnService;
        this.objectMapper = objectMapper;
    }

    public Mono<ServerResponse> listReports(ServerRequest request) {
        return request.principal()
                .flatMap(principal -> processRequest(principal, request.queryParam("date").orElseThrow()))
                .flatMap(cdnUrl -> ServerResponse.ok()
                        .bodyValue(cdnUrl))
                .switchIfEmpty(ServerResponse.notFound()
                        .build());
    }

    private Mono<String> processRequest(Principal principal, String reportDateString) {
        String userId = ((JwtAuthenticationToken) principal).getToken().getClaimAsString("preferred_username");
        LocalDate reportDate = LocalDate.parse(reportDateString);

        String s3Key = s3Service.buildKey(userId, reportDate);
        String cdnUrl = cdnService.buildUrl(userId, reportDate);

        if (s3Service.exists(s3Key)) {
            return Mono.just(cdnUrl);
        }

        return reportService.findAllByUserId(userId)
                .collectList()
                .filter(reportEntries -> !reportEntries.isEmpty())
                .doOnNext(reportEntries -> s3Service.upload(s3Key, objectMapper.writeValueAsBytes(reportEntries)))
                .map(reportEntries -> cdnUrl);
    }

}
