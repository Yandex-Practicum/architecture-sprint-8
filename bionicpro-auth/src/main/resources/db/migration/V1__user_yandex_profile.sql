CREATE TABLE user_yandex_profile (
    id BIGSERIAL PRIMARY KEY,
    keycloak_subject VARCHAR(255) NOT NULL UNIQUE,
    yandex_id VARCHAR(128),
    email VARCHAR(512),
    display_name VARCHAR(512),
    first_name VARCHAR(256),
    last_name VARCHAR(256),
    avatar_url VARCHAR(2048),
    profile_json TEXT,
    consent_accepted BOOLEAN NOT NULL DEFAULT FALSE,
    consent_accepted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_user_yandex_profile_subject ON user_yandex_profile (keycloak_subject);
