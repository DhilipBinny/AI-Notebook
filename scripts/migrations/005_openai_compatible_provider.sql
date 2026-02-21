-- Migration 005: Replace 'ollama' provider with 'openai_compatible'
-- Adds base_url column and renames the provider enum value
-- Run: docker exec ainotebook-mysql mysql -uroot -painotebook_dev_password ainotebook < scripts/migrations/005_openai_compatible_provider.sql

-- Step 1: Add base_url column to both key tables
ALTER TABLE user_api_keys ADD COLUMN base_url VARCHAR(500) NULL AFTER model_override;
ALTER TABLE platform_api_keys ADD COLUMN base_url VARCHAR(500) NULL AFTER model_name;

-- Step 2: Expand ENUMs to include new value (keep old for data migration)
ALTER TABLE user_api_keys MODIFY COLUMN provider ENUM('openai','anthropic','gemini','ollama','openai_compatible') NOT NULL;
ALTER TABLE platform_api_keys MODIFY COLUMN provider ENUM('openai','anthropic','gemini','ollama','openai_compatible') NOT NULL;
ALTER TABLE projects MODIFY COLUMN llm_provider ENUM('ollama','openai','anthropic','gemini','openai_compatible') NOT NULL DEFAULT 'gemini';

-- Step 3: Migrate existing data
UPDATE user_api_keys SET provider = 'openai_compatible' WHERE provider = 'ollama';
UPDATE platform_api_keys SET provider = 'openai_compatible' WHERE provider = 'ollama';
UPDATE projects SET llm_provider = 'openai_compatible' WHERE llm_provider = 'ollama';
UPDATE llm_pricing SET provider = 'openai_compatible' WHERE provider = 'ollama';

-- Step 4: Shrink ENUMs (remove old 'ollama' value)
ALTER TABLE user_api_keys MODIFY COLUMN provider ENUM('openai','anthropic','gemini','openai_compatible') NOT NULL;
ALTER TABLE platform_api_keys MODIFY COLUMN provider ENUM('openai','anthropic','gemini','openai_compatible') NOT NULL;
ALTER TABLE projects MODIFY COLUMN llm_provider ENUM('openai','anthropic','gemini','openai_compatible') NOT NULL DEFAULT 'gemini';
