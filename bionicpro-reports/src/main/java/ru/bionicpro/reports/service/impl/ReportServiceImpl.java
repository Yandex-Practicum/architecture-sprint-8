package ru.bionicpro.reports.service.impl;

import jakarta.xml.bind.JAXBContext;
import jakarta.xml.bind.Marshaller;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import ru.bionicpro.reports.dto.ReportXml;
import ru.bionicpro.reports.model.ReportResponse;
import ru.bionicpro.reports.model.UserReport;
import ru.bionicpro.reports.repository.ReportRepository;
import ru.bionicpro.reports.service.ReportService;
import ru.bionicpro.reports.service.S3StorageService;

import java.io.StringWriter;
import java.time.LocalDate;

@Slf4j
@Service
@RequiredArgsConstructor
public class ReportServiceImpl implements ReportService {

    private final ReportRepository reportRepository;
    private final S3StorageService s3StorageService;

    @Override
    public ReportResponse getReportWithUrl(String userId, String format) {
        LocalDate date = LocalDate.now();

        // 1. Проверяем наличие отчёта в S3
        if (s3StorageService.reportExists(userId, date, format)) {
            log.info("Report found in S3 cache for user: {}", userId);
            String url = s3StorageService.getReportUrl(userId, date, format);

            // Делаем HEAD запрос к Nginx, чтобы получить статус кеша
            String cacheStatus = s3StorageService.getCacheStatus(url);

            return ReportResponse.builder()
                    .url(url)
                    .cached(true)
                    .cacheStatus(cacheStatus)
                    .build();
        }

        // 2. Отчёт не найден - генерируем
        log.info("Report not in cache, generating for user: {}", userId);

        String xmlContent = exportReportToXml(userId);

        // 3. Сохраняем в S3
        s3StorageService.saveXmlReport(userId, date, xmlContent);

        // 4. Возвращаем ссылку на свежесозданный отчёт
        String url = s3StorageService.getReportUrl(userId, date, format);

        // Делаем HEAD запрос к Nginx, чтобы получить статус кеша
        String cacheStatus = s3StorageService.getCacheStatus(url);

        return ReportResponse.builder()
                .url(url)
                .cached(false)
                .cacheStatus(cacheStatus)
                .build();
    }

    @Override
    public String exportReportToXml(String userId) {
        try {
            // Получаем данные пользователя из репозитория
            UserReport userReport = reportRepository.findById(userId)
                    .orElseThrow(() -> new RuntimeException("User not found: " + userId));

            // Создаём XML объект
            ReportXml reportXml = new ReportXml(userReport);

            // Маршаллинг в XML строку
            JAXBContext context = JAXBContext.newInstance(ReportXml.class);
            Marshaller marshaller = context.createMarshaller();
            marshaller.setProperty(Marshaller.JAXB_FORMATTED_OUTPUT, Boolean.TRUE);
            marshaller.setProperty(Marshaller.JAXB_ENCODING, "UTF-8");

            StringWriter sw = new StringWriter();
            marshaller.marshal(reportXml, sw);

            return sw.toString();

        } catch (Exception e) {
            log.error("Error generating XML for user: {}", userId, e);
            throw new RuntimeException("Failed to generate XML report", e);
        }
    }

}