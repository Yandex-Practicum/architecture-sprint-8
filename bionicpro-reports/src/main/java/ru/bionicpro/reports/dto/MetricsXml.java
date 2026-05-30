package ru.bionicpro.reports.dto;

import jakarta.xml.bind.annotation.XmlAccessType;
import jakarta.xml.bind.annotation.XmlAccessorType;
import jakarta.xml.bind.annotation.XmlElement;
import lombok.Data;
import ru.bionicpro.reports.model.UserReport;

import static java.util.Objects.requireNonNullElse;

@Data
@XmlAccessorType(XmlAccessType.FIELD)
public class MetricsXml {

    @XmlElement(name = "totalMovements")
    private Integer totalMovements;

    @XmlElement(name = "avgReactionTime")
    private Double avgReactionTime;

    @XmlElement(name = "medianReactionTime")
    private Double medianReactionTime;

    @XmlElement(name = "minReactionTime")
    private Integer minReactionTime;

    @XmlElement(name = "maxReactionTime")
    private Integer maxReactionTime;

    @XmlElement(name = "avgSignalQuality")
    private Double avgSignalQuality;

    @XmlElement(name = "minSignalQuality")
    private Double minSignalQuality;

    @XmlElement(name = "avgBatteryLevel")
    private Integer avgBatteryLevel;

    @XmlElement(name = "performanceScore")
    private Double performanceScore;

    @XmlElement(name = "needsCalibration")
    private Boolean needsCalibration;

    @XmlElement(name = "lastActivityDate")
    private String lastActivityDate;

    public MetricsXml() {
    }

    public MetricsXml(UserReport report) {
        this.totalMovements = requireNonNullElse(report.getTotalMovements(), 0);
        this.avgReactionTime = requireNonNullElse(report.getAvgReactionTime(), 0.0);
        this.medianReactionTime = requireNonNullElse(report.getMedianReactionTime(), 0.0);
        this.minReactionTime = requireNonNullElse(report.getMinReactionTime(), 0);
        this.maxReactionTime = requireNonNullElse(report.getMaxReactionTime(), 0);
        this.avgSignalQuality = requireNonNullElse(report.getAvgSignalQuality(), 0.0);
        this.minSignalQuality = requireNonNullElse(report.getMinSignalQuality(), 0.0);
        this.avgBatteryLevel = requireNonNullElse(report.getAvgBatteryLevel(), 0);
        this.performanceScore = requireNonNullElse(report.getPerformanceScore(), 0.0);
        this.needsCalibration = requireNonNullElse(report.getNeedsCalibration(), false);
        this.lastActivityDate = report.getLastActiveDate() != null ?
                report.getLastActiveDate().toString() : null;
    }
}
