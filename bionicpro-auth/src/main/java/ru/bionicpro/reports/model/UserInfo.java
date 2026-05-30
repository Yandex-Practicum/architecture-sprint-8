package ru.bionicpro.reports.model;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;

public class UserInfo {
    private String sub;

    @JsonProperty("preferred_username")
    private String preferredUsername;

    private String email;

    @JsonProperty("realm_access")
    private RealmAccess realmAccess;

    public UserInfo() {
    }

    // Геттеры и сеттеры
    public String getSub() {
        return sub;
    }

    public void setSub(String sub) {
        this.sub = sub;
    }

    public String getPreferredUsername() {
        return preferredUsername;
    }

    public void setPreferredUsername(String preferredUsername) {
        this.preferredUsername = preferredUsername;
    }

    public String getEmail() {
        return email;
    }

    public void setEmail(String email) {
        this.email = email;
    }

    public RealmAccess getRealmAccess() {
        return realmAccess;
    }

    public void setRealmAccess(RealmAccess realmAccess) {
        this.realmAccess = realmAccess;
    }

    public static class RealmAccess {
        private List<String> roles;

        public RealmAccess() {
        }

        public List<String> getRoles() {
            return roles;
        }

        public void setRoles(List<String> roles) {
            this.roles = roles;
        }
    }
}