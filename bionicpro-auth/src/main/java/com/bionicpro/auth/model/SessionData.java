package com.bionicpro.auth.model;

import java.time.Instant;

public class SessionData {

    private String accessToken;
    private String refreshToken;
    private Instant accessTokenExpiry;
    private final Instant sessionExpiry;

    public SessionData(String accessToken, String refreshToken,
                       Instant accessTokenExpiry, Instant sessionExpiry) {
        this.accessToken = accessToken;
        this.refreshToken = refreshToken;
        this.accessTokenExpiry = accessTokenExpiry;
        this.sessionExpiry = sessionExpiry;
    }

    public boolean isAccessTokenExpired() {
        // Use 10-second buffer to avoid races
        return Instant.now().isAfter(accessTokenExpiry.minusSeconds(10));
    }

    public boolean isSessionExpired() {
        return Instant.now().isAfter(sessionExpiry);
    }

    public void updateTokens(String newAccessToken, String newRefreshToken, Instant newExpiry) {
        this.accessToken = newAccessToken;
        this.refreshToken = newRefreshToken;
        this.accessTokenExpiry = newExpiry;
    }

    public String getAccessToken() { return accessToken; }
    public String getRefreshToken() { return refreshToken; }
    public Instant getAccessTokenExpiry() { return accessTokenExpiry; }
    public Instant getSessionExpiry() { return sessionExpiry; }
}
