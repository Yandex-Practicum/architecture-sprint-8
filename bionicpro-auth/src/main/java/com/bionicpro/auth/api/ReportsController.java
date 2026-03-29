package com.bionicpro.auth.api;

import com.bionicpro.auth.web.SessionAuthenticationFilter;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestAttribute;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api")
public class ReportsController {

    @GetMapping("/reports")
    public ResponseEntity<Map<String, Object>> reports(
            @RequestAttribute(SessionAuthenticationFilter.ATTR_ACCESS_TOKEN) String accessToken) {
        // Пример: дальше можно вызвать reports-api с Authorization: Bearer accessToken
        return ResponseEntity.ok(Map.of(
                "status", "ok",
                "message", "Используйте access_token на стороне сервера для вызова защищённых API"
        ));
    }
}
