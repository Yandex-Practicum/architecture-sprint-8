package ru.bionicpro.reports.model;

import com.fasterxml.jackson.annotation.JsonProperty;

public class TokenResponse {
    @JsonProperty("access_token")
    private String accessToken;

    @JsonProperty("refresh_token")
    private String refreshToken;

    @JsonProperty("expires_in")
    private int expiresIn;

    @JsonProperty("refresh_expires_in")
    private int refreshExpiresIn;

    @JsonProperty("token_type")
    private String tokenType;

    @JsonProperty("session_state")
    private String sessionState;

    private String scope;

    public TokenResponse() {
    }

    // Геттеры
    public String getAccessToken() {
        return accessToken;
    }

    public String getRefreshToken() {
        return refreshToken;
    }

    public int getExpiresIn() {
        return expiresIn;
    }

    public int getRefreshExpiresIn() {
        return refreshExpiresIn;
    }

    public String getTokenType() {
        return tokenType;
    }

    public String getSessionState() {
        return sessionState;
    }

    public String getScope() {
        return scope;
    }

    // Сеттеры
    public void setAccessToken(String accessToken) {
        this.accessToken = accessToken;
    }

    public void setRefreshToken(String refreshToken) {
        this.refreshToken = refreshToken;
    }

    public void setExpiresIn(int expiresIn) {
        this.expiresIn = expiresIn;
    }

    public void setRefreshExpiresIn(int refreshExpiresIn) {
        this.refreshExpiresIn = refreshExpiresIn;
    }

    public void setTokenType(String tokenType) {
        this.tokenType = tokenType;
    }

    public void setSessionState(String sessionState) {
        this.sessionState = sessionState;
    }

    public void setScope(String scope) {
        this.scope = scope;
    }
}