-- Migration 008: Allow multiple API keys per provider per user
-- Drop unique constraint (user_id, provider) to allow multiple keys

-- Drop the unique constraint
ALTER TABLE user_api_keys DROP INDEX uk_user_api_keys_provider;

-- Add label column for distinguishing keys
ALTER TABLE user_api_keys ADD COLUMN label VARCHAR(100) NULL AFTER provider;

-- Add composite index for queries (non-unique)
ALTER TABLE user_api_keys ADD INDEX idx_user_api_keys_user_provider (user_id, provider);
