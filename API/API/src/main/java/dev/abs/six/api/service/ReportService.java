package dev.abs.six.api.service;

import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class ReportService {

    public String getReport() {
        return "Successfull report";
    }
}
