package ru.bionicpro.reports.model;

import java.io.Serializable;
import java.time.Instant;
import java.util.List;

public class AuthSession implements Serializable {

    private static final long serialVersionUID = 1L;

    private String sessionId;
    private String userId;
    private String username;
    private String email;
    private String accessToken;
    private Instant accessTokenExpiry;
    private String encryptedRefreshToken;
    private List<String> realmRoles;
    private Instant createdAt;
    private Instant lastRotatedAt;
    private boolean active;

    // Пустой конструктор
    public AuthSession() {
    }

    // Геттеры
    public String getSessionId() {
        return sessionId;
    }

    public String getUserId() {
        return userId;
    }

    public String getUsername() {
        return username;
    }

    public String getEmail() {
        return email;
    }

    public String getAccessToken() {
        return accessToken;
    }

    public Instant getAccessTokenExpiry() {
        return accessTokenExpiry;
    }

    public String getEncryptedRefreshToken() {
        return encryptedRefreshToken;
    }

    public List<String> getRealmRoles() {
        return realmRoles;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getLastRotatedAt() {
        return lastRotatedAt;
    }

    public boolean isActive() {
        return active;
    }

    // Сеттеры
    public void setSessionId(String sessionId) {
        this.sessionId = sessionId;
    }

    public void setUserId(String userId) {
        this.userId = userId;
    }

    public void setUsername(String username) {
        this.username = username;
    }

    public void setEmail(String email) {
        this.email = email;
    }

    public void setAccessToken(String accessToken) {
        this.accessToken = accessToken;
    }

    public void setAccessTokenExpiry(Instant accessTokenExpiry) {
        this.accessTokenExpiry = accessTokenExpiry;
    }

    public void setEncryptedRefreshToken(String encryptedRefreshToken) {
        this.encryptedRefreshToken = encryptedRefreshToken;
    }

    public void setRealmRoles(List<String> realmRoles) {
        this.realmRoles = realmRoles;
    }

    public void setCreatedAt(Instant createdAt) {
        this.createdAt = createdAt;
    }

    public void setLastRotatedAt(Instant lastRotatedAt) {
        this.lastRotatedAt = lastRotatedAt;
    }

    public void setActive(boolean active) {
        this.active = active;
    }
}