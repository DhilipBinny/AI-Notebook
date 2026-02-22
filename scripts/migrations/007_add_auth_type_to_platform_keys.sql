-- Migration 007: Add auth_type column to platform_api_keys
-- Supports OAuth tokens (sk-ant-oat01-...) for Anthropic alongside standard API keys.
-- Default is 'api_key' so existing keys are unaffected.

ALTER TABLE platform_api_keys
    ADD COLUMN auth_type ENUM('api_key','oauth_token') NOT NULL DEFAULT 'api_key'
    AFTER api_key_hint;
