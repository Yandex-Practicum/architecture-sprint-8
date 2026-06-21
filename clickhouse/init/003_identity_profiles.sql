CREATE TABLE IF NOT EXISTS bionicpro.identity_profiles
(
    subject String,
    username String,
    email String,
    full_name String,
    identity_provider LowCardinality(String),
    raw_profile String,
    saved_at DateTime
)
ENGINE = ReplacingMergeTree(saved_at)
ORDER BY (identity_provider, subject);
