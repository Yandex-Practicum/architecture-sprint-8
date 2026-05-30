package ru.bionicpro.reports.controller;

import jakarta.servlet.http.HttpServletRequest;
import org.springframework.boot.web.servlet.error.ErrorController;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.HashMap;
import java.util.Map;

@RestController
public class CustomErrorController implements ErrorController {

    @RequestMapping("/error")
    public ResponseEntity<Map<String, Object>> handleError(HttpServletRequest request) {
        Integer statusCode = (Integer) request.getAttribute("jakarta.servlet.error.status_code");
        Exception error = (Exception) request.getAttribute("jakarta.servlet.error.exception");

        Map<String, Object> errorResponse = new HashMap<>();
        errorResponse.put("success", false);
        errorResponse.put("status", statusCode != null ? statusCode : 500);
        errorResponse.put("message", error != null ? error.getMessage() : "Unknown error");
        errorResponse.put("path", request.getAttribute("jakarta.servlet.error.request_uri"));

        HttpStatus status = statusCode != null ? HttpStatus.valueOf(statusCode) : HttpStatus.INTERNAL_SERVER_ERROR;
        return new ResponseEntity<>(errorResponse, status);
    }
}
