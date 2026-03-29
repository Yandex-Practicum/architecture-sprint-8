package com.bionicpro.auth.api;

import com.bionicpro.auth.web.SessionAuthenticationFilter;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestAttribute;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api")
public class SessionController {

    @GetMapping("/session")
    public Map<String, Object> session(
            @RequestAttribute(SessionAuthenticationFilter.ATTR_SUBJECT) String subject) {
        return Map.of(
                "authenticated", true,
                "subject", subject
        );
    }
}
