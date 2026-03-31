package com.bionicpro.auth.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "app")
public class AppProperties {

    private String frontendUrl = "http://localhost:3000";
    private String sessionCookieName = "BIONIC_SESSION";
    private int sessionMaxAgeSeconds = 1800;
    private boolean cookieSecure = true;
    private String encryptionSecret = "";
    /**
     * Базовый URL сервиса отчётов (bionicpro-reports), без завершающего слэша.
     */
    private String reportsServiceBaseUrl = "http://localhost:8082";

    public String getFrontendUrl() {
        return frontendUrl;
    }

    public void setFrontendUrl(String frontendUrl) {
        this.frontendUrl = frontendUrl;
    }

    public String getSessionCookieName() {
        return sessionCookieName;
    }

    public void setSessionCookieName(String sessionCookieName) {
        this.sessionCookieName = sessionCookieName;
    }

    public int getSessionMaxAgeSeconds() {
        return sessionMaxAgeSeconds;
    }

    public void setSessionMaxAgeSeconds(int sessionMaxAgeSeconds) {
        this.sessionMaxAgeSeconds = sessionMaxAgeSeconds;
    }

    public boolean isCookieSecure() {
        return cookieSecure;
    }

    public void setCookieSecure(boolean cookieSecure) {
        this.cookieSecure = cookieSecure;
    }

    public String getEncryptionSecret() {
        return encryptionSecret;
    }

    public void setEncryptionSecret(String encryptionSecret) {
        this.encryptionSecret = encryptionSecret;
    }

    public String getReportsServiceBaseUrl() {
        return reportsServiceBaseUrl;
    }

    public void setReportsServiceBaseUrl(String reportsServiceBaseUrl) {
        this.reportsServiceBaseUrl = reportsServiceBaseUrl;
    }
}
