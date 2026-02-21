-- Migration 004: Add platform_api_keys table
-- Platform-level API keys stored encrypted in DB (replaces env var approach)
-- Multiple keys per provider allowed, one active per provider

CREATE TABLE IF NOT EXISTS platform_api_keys (
    id CHAR(36) NOT NULL PRIMARY KEY,
    provider ENUM('openai','anthropic','gemini','ollama') NOT NULL,
    label VARCHAR(100) NOT NULL,
    api_key_encrypted TEXT NOT NULL,
    api_key_hint VARCHAR(20) NOT NULL,
    model_name VARCHAR(100) NULL,
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    priority INT NOT NULL DEFAULT 0,
    created_by CHAR(36) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_platform_keys_provider_active (provider, is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
