package com.bionicpro.auth.web;

import java.time.Instant;
import java.util.List;

public record SessionInfo(String username, List<String> roles, Instant accessTokenExpiresAt) {
}
