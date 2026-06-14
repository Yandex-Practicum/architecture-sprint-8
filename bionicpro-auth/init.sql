-- BionicPRO User Profiles Database Schema
-- Stores user profile data from external identity providers (Yandex ID, etc.)

-- User profiles table
CREATE TABLE IF NOT EXISTS user_profiles (
    id SERIAL PRIMARY KEY,
    -- Keycloak user ID (sub claim)
    keycloak_user_id VARCHAR(255) UNIQUE NOT NULL,
    -- Identity provider that was used for authentication
    identity_provider VARCHAR(50),
    -- Yandex ID specific fields
    yandex_id VARCHAR(50),
    yandex_login VARCHAR(100),
    yandex_avatar_id VARCHAR(255),
    -- Common profile fields
    email VARCHAR(255),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    display_name VARCHAR(200),
    phone VARCHAR(50),
    -- Profile metadata
    avatar_url VARCHAR(500),
    -- Consent tracking
    consent_given BOOLEAN DEFAULT FALSE,
    consent_given_at TIMESTAMP,
    consent_scopes TEXT[], -- Array of scopes user consented to
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP
);

-- Index for fast lookups by Keycloak user ID
CREATE INDEX IF NOT EXISTS idx_user_profiles_keycloak_user_id ON user_profiles(keycloak_user_id);

-- Index for fast lookups by Yandex ID
CREATE INDEX IF NOT EXISTS idx_user_profiles_yandex_id ON user_profiles(yandex_id);

-- Index for identity provider filtering
CREATE INDEX IF NOT EXISTS idx_user_profiles_identity_provider ON user_profiles(identity_provider);

-- Federated identity links table (for users who linked multiple IdPs)
CREATE TABLE IF NOT EXISTS federated_identities (
    id SERIAL PRIMARY KEY,
    user_profile_id INTEGER REFERENCES user_profiles(id) ON DELETE CASCADE,
    identity_provider VARCHAR(50) NOT NULL,
    provider_user_id VARCHAR(255) NOT NULL,
    provider_username VARCHAR(255),
    token_expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(identity_provider, provider_user_id)
);

-- Index for fast federated identity lookups
CREATE INDEX IF NOT EXISTS idx_federated_identities_provider ON federated_identities(identity_provider, provider_user_id);

-- User consent history table (audit trail)
CREATE TABLE IF NOT EXISTS consent_history (
    id SERIAL PRIMARY KEY,
    user_profile_id INTEGER REFERENCES user_profiles(id) ON DELETE CASCADE,
    client_id VARCHAR(255) NOT NULL,
    scopes TEXT[] NOT NULL,
    action VARCHAR(20) NOT NULL, -- 'granted', 'revoked'
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for consent history lookups
CREATE INDEX IF NOT EXISTS idx_consent_history_user ON consent_history(user_profile_id);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger to auto-update updated_at
DROP TRIGGER IF EXISTS update_user_profiles_updated_at ON user_profiles;
CREATE TRIGGER update_user_profiles_updated_at
    BEFORE UPDATE ON user_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Comments for documentation
COMMENT ON TABLE user_profiles IS 'Stores user profile data synchronized from external identity providers';
COMMENT ON TABLE federated_identities IS 'Links user profiles to multiple external identity providers';
COMMENT ON TABLE consent_history IS 'Audit trail of user consent actions';
COMMENT ON COLUMN user_profiles.keycloak_user_id IS 'Unique user identifier from Keycloak (sub claim)';
COMMENT ON COLUMN user_profiles.identity_provider IS 'The IdP used for initial authentication (yandex, google, etc.)';
COMMENT ON COLUMN user_profiles.consent_scopes IS 'Array of OAuth scopes the user has consented to';
