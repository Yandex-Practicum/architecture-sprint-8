CREATE TABLE IF NOT EXISTS user_profiles (
    id SERIAL PRIMARY KEY,
    keycloak_user_id VARCHAR(255) UNIQUE NOT NULL,
    yandex_id VARCHAR(255),
    username VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    display_name VARCHAR(255),
    avatar_url VARCHAR(1024),
    phone VARCHAR(50),
    yandex_login VARCHAR(255),
    consent_given BOOLEAN DEFAULT FALSE,
    consent_given_at TIMESTAMP,
    profile_fetched_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_user_profiles_keycloak_id ON user_profiles(keycloak_user_id);
CREATE INDEX idx_user_profiles_yandex_id ON user_profiles(yandex_id);
