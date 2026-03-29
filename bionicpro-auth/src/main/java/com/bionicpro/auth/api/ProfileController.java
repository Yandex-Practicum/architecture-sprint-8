package com.bionicpro.auth.api;

import com.bionicpro.auth.profile.UserProfileService;
import com.bionicpro.auth.web.SessionAuthenticationFilter;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestAttribute;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.util.Map;

@RestController
@RequestMapping("/api/profile")
public class ProfileController {

    private final UserProfileService userProfileService;

    public ProfileController(UserProfileService userProfileService) {
        this.userProfileService = userProfileService;
    }

    @GetMapping("/status")
    public Map<String, Object> status(
            @RequestAttribute(SessionAuthenticationFilter.ATTR_ACCESS_TOKEN) String accessToken,
            @RequestAttribute(SessionAuthenticationFilter.ATTR_SUBJECT) String subject) {
        try {
            UserProfileService.ProfileStatusDto s = userProfileService.buildStatus(subject, accessToken);
            if (!s.needsConsent() && s.consentAccepted()) {
                return Map.of(
                        "needsConsent", false,
                        "consentAccepted", true);
            }
            UserProfileService.PreviewDto p = s.preview();
            return Map.of(
                    "needsConsent", s.needsConsent(),
                    "consentAccepted", false,
                    "preview", p != null
                            ? Map.of(
                                    "email", p.email() != null ? p.email() : "",
                                    "displayName", p.displayName() != null ? p.displayName() : "")
                            : Map.of());
        } catch (Exception e) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "UserInfo недоступен: " + e.getMessage());
        }
    }

    @PostMapping("/consent")
    public Map<String, Object> consent(
            @RequestAttribute(SessionAuthenticationFilter.ATTR_ACCESS_TOKEN) String accessToken,
            @RequestAttribute(SessionAuthenticationFilter.ATTR_SUBJECT) String subject,
            @RequestBody ConsentRequest body) {
        try {
            userProfileService.recordConsent(subject, accessToken, body.accept());
            return Map.of("ok", true, "consentAccepted", body.accept());
        } catch (Exception e) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "Не удалось сохранить профиль: " + e.getMessage());
        }
    }

    public record ConsentRequest(boolean accept) {}
}
