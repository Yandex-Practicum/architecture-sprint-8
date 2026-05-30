package ru.bionicpro.reports.dto;

import jakarta.xml.bind.annotation.XmlAccessType;
import jakarta.xml.bind.annotation.XmlAccessorType;
import jakarta.xml.bind.annotation.XmlElement;
import jakarta.xml.bind.annotation.XmlRootElement;
import lombok.Data;
import ru.bionicpro.reports.model.UserReport;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

@Data
@XmlRootElement(name = "report")
@XmlAccessorType(XmlAccessType.FIELD)
public class ReportXml {

    @XmlElement(name = "user")
    private UserXml user;

    @XmlElement(name = "metrics")
    private MetricsXml metrics;

    @XmlElement(name = "generatedAt")
    private String generatedAt;

    public ReportXml() {
    }

    public ReportXml(UserReport report) {
        this.user = new UserXml(report);
        this.metrics = new MetricsXml(report);
        this.generatedAt = LocalDateTime.now().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME);
    }
}