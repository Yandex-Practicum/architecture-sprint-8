package dev.abs.six.api.controller;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import dev.abs.six.api.service.ReportService;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Base64;
import java.util.List;
import java.util.stream.Collectors;
import java.util.stream.StreamSupport;


@RestController
@RequestMapping("/reports")
@RequiredArgsConstructor
public class ReportController {
    private final ReportService reportService;

    private static final Logger logger = LoggerFactory.getLogger(ReportController.class);

    @CrossOrigin(origins = "http://localhost:3000")
    @GetMapping()
    @ResponseStatus(HttpStatus.OK)
    public ResponseEntity getReport(@RequestHeader("Authorization") String bearerToken) throws JsonProcessingException {
        logger.info("got request from {}", bearerToken);

        String[] chunks = bearerToken.split("\\.");
        Base64.Decoder decoder = Base64.getUrlDecoder();
        String payload = new String(decoder.decode(chunks[1]));
        ArrayNode roles = (ArrayNode)new ObjectMapper().readTree(payload).get("realm_access").get("roles");
        List<String> objects = StreamSupport
                .stream(roles.spliterator(), false)
                .map(JsonNode::asText)
                .toList();
        if (objects.get(0).equals("prothetic_user")) {
            return new ResponseEntity<>(reportService.getReport(), HttpStatus.OK);
        } else {
            logger.info("report is not allowed for this user");
            return new ResponseEntity<>(null, HttpStatus.FORBIDDEN);
        }
    }
}
