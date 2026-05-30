package ru.bionicpro.reports.dto;

import jakarta.xml.bind.annotation.XmlAccessType;
import jakarta.xml.bind.annotation.XmlAccessorType;
import jakarta.xml.bind.annotation.XmlElement;
import lombok.Data;
import ru.bionicpro.reports.model.UserReport;

@Data
@XmlAccessorType(XmlAccessType.FIELD)
public class UserXml {

    @XmlElement(name = "id")
    private String id;

    @XmlElement(name = "name")
    private String name;

    @XmlElement(name = "email")
    private String email;

    @XmlElement(name = "phone")
    private String phone;

    @XmlElement(name = "prosthesisModel")
    private String prosthesisModel;

    @XmlElement(name = "serialNumber")
    private String serialNumber;

    @XmlElement(name = "registrationDate")
    private String registrationDate;

    public UserXml() {
    }

    public UserXml(UserReport report) {
        this.id = report.getUserId();
        this.name = report.getUserName();
        this.email = report.getEmail();
        this.phone = report.getPhone();
        this.prosthesisModel = report.getProsthesisModel();
        this.serialNumber = report.getSerialNumber();
        this.registrationDate = report.getRegistrationDate() != null ?
                report.getRegistrationDate().toString() : null;
    }
}
