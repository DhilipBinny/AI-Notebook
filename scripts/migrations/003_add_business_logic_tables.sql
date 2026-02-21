-- =====================================================
-- Migration 003: Business Logic Tables
-- =====================================================
-- Adds: is_admin to users, invitations, invitation_uses,
--        user_api_keys, user_credits, llm_pricing,
--        usage_records, notebook_templates
-- Alters: playgrounds (user_id, nullable project_id)
--
-- Run: mysql -u root -p ainotebook < scripts/migrations/003_add_business_logic_tables.sql
-- =====================================================

USE ainotebook;

-- =====================================================
-- ALTER: users - add is_admin column
-- =====================================================
ALTER TABLE users
    ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT FALSE AFTER is_verified;


-- =====================================================
-- TABLE: invitations
-- =====================================================
-- Invite codes for controlled user onboarding
-- =====================================================
CREATE TABLE IF NOT EXISTS invitations (
    id CHAR(36) NOT NULL,

    -- Unique invite code (generated via secrets.token_urlsafe)
    code VARCHAR(64) NOT NULL,

    -- Optional: lock to specific email
    email VARCHAR(255) NULL,

    -- Usage limits
    max_uses INT NOT NULL DEFAULT 1,
    used_count INT NOT NULL DEFAULT 0,

    -- Creator
    created_by CHAR(36) NOT NULL,

    -- Validity
    expires_at TIMESTAMP NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    -- Admin note
    note VARCHAR(500) NULL,

    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    UNIQUE KEY uk_invitations_code (code),
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_invitations_email (email),
    INDEX idx_invitations_active (is_active),
    INDEX idx_invitations_created_by (created_by)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =====================================================
-- TABLE: invitation_uses
-- =====================================================
-- Tracks which users redeemed which invitations
-- =====================================================
CREATE TABLE IF NOT EXISTS invitation_uses (
    id CHAR(36) NOT NULL,

    invitation_id CHAR(36) NOT NULL,
    user_id CHAR(36) NOT NULL,

    used_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    FOREIGN KEY (invitation_id) REFERENCES invitations(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_invitation_uses_invitation (invitation_id),
    INDEX idx_invitation_uses_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =====================================================
-- ALTER: playgrounds - add user_id, make project_id nullable
-- =====================================================
-- Step 1: Add user_id column (nullable first for existing rows)
ALTER TABLE playgrounds
    ADD COLUMN user_id CHAR(36) NULL AFTER id;

-- Step 2: Populate user_id from project's user_id for any existing rows
UPDATE playgrounds p
    JOIN projects pr ON p.project_id = pr.id
    SET p.user_id = pr.user_id;

-- Step 3: Make user_id NOT NULL and add constraints
ALTER TABLE playgrounds
    MODIFY COLUMN user_id CHAR(36) NOT NULL,
    ADD FOREIGN KEY fk_playgrounds_user (user_id) REFERENCES users(id) ON DELETE CASCADE,
    ADD UNIQUE KEY uk_playgrounds_user (user_id);

-- Step 4: Make project_id nullable (becomes "active project")
ALTER TABLE playgrounds
    MODIFY COLUMN project_id CHAR(36) NULL,
    DROP FOREIGN KEY playgrounds_ibfk_1,
    ADD FOREIGN KEY fk_playgrounds_project (project_id) REFERENCES projects(id) ON DELETE SET NULL;

-- Step 5: Drop old unique constraint on project_id (no longer 1:1)
ALTER TABLE playgrounds
    DROP INDEX uk_playgrounds_project;

-- Add index on project_id (non-unique now)
ALTER TABLE playgrounds
    ADD INDEX idx_playgrounds_project (project_id);


-- =====================================================
-- TABLE: user_api_keys
-- =====================================================
-- Stores user-owned LLM API keys (Fernet encrypted)
-- =====================================================
CREATE TABLE IF NOT EXISTS user_api_keys (
    id CHAR(36) NOT NULL,

    user_id CHAR(36) NOT NULL,
    provider ENUM('openai', 'anthropic', 'gemini', 'ollama') NOT NULL,

    -- Encrypted API key (Fernet / AES-128-CBC)
    api_key_encrypted TEXT NOT NULL,
    -- Masked display hint (e.g., "sk-...a1b2")
    api_key_hint VARCHAR(20) NOT NULL,

    -- Optional model override
    model_override VARCHAR(100) NULL,

    -- State
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_validated BOOLEAN NOT NULL DEFAULT FALSE,
    last_validated_at TIMESTAMP NULL,

    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY uk_user_api_keys_provider (user_id, provider),
    INDEX idx_user_api_keys_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =====================================================
-- TABLE: user_credits
-- =====================================================
-- One row per user, tracks credit balance
-- =====================================================
CREATE TABLE IF NOT EXISTS user_credits (
    user_id CHAR(36) NOT NULL,

    -- Balance in cents (1000 = $10.00)
    balance_cents INT NOT NULL DEFAULT 1000,
    total_deposited_cents INT NOT NULL DEFAULT 1000,
    total_consumed_cents INT NOT NULL DEFAULT 0,

    last_charged_at TIMESTAMP NULL,

    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (user_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =====================================================
-- TABLE: llm_pricing
-- =====================================================
-- Per-model pricing with configurable margin
-- =====================================================
CREATE TABLE IF NOT EXISTS llm_pricing (
    id INT NOT NULL AUTO_INCREMENT,

    provider VARCHAR(50) NOT NULL,
    model VARCHAR(100) NOT NULL,

    -- Cost per 1M tokens in cents
    input_cost_per_1m_cents INT NOT NULL,
    output_cost_per_1m_cents INT NOT NULL,

    -- Margin multiplier (1.30 = 30% margin)
    margin_multiplier DECIMAL(3,2) NOT NULL DEFAULT 1.30,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    UNIQUE KEY uk_llm_pricing_model (provider, model),
    INDEX idx_llm_pricing_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =====================================================
-- TABLE: usage_records
-- =====================================================
-- Per-request LLM usage tracking
-- =====================================================
CREATE TABLE IF NOT EXISTS usage_records (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,

    user_id CHAR(36) NOT NULL,
    project_id CHAR(36) NULL,

    -- LLM info
    provider VARCHAR(50) NOT NULL,
    model VARCHAR(100) NOT NULL,
    request_type ENUM('chat', 'ai_cell', 'summarize') NOT NULL DEFAULT 'chat',

    -- Token counts
    input_tokens INT NOT NULL DEFAULT 0,
    output_tokens INT NOT NULL DEFAULT 0,
    cached_tokens INT NOT NULL DEFAULT 0,

    -- Cost (in cents)
    cost_cents INT NOT NULL DEFAULT 0,       -- Charged to user (with margin)
    raw_cost_cents INT NOT NULL DEFAULT 0,   -- Actual API cost

    -- Whether user used their own API key
    is_own_key BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_usage_user (user_id),
    INDEX idx_usage_project (project_id),
    INDEX idx_usage_created (created_at),
    INDEX idx_usage_provider (provider, model),
    INDEX idx_usage_user_created (user_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =====================================================
-- TABLE: notebook_templates
-- =====================================================
-- Pre-built notebook templates for courses/workshops
-- =====================================================
CREATE TABLE IF NOT EXISTS notebook_templates (
    id CHAR(36) NOT NULL,

    name VARCHAR(255) NOT NULL,
    description TEXT NULL,
    category VARCHAR(100) NULL,

    -- S3 storage path
    storage_path VARCHAR(500) NOT NULL,

    -- Display
    thumbnail_url VARCHAR(500) NULL,
    difficulty_level ENUM('beginner', 'intermediate', 'advanced') NOT NULL DEFAULT 'beginner',
    estimated_minutes INT NULL,
    tags JSON NULL,

    -- State
    is_public BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order INT NOT NULL DEFAULT 0,

    -- Creator
    created_by CHAR(36) NULL,

    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_templates_public (is_public),
    INDEX idx_templates_category (category),
    INDEX idx_templates_sort (sort_order),
    INDEX idx_templates_created_by (created_by)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =====================================================
-- SEED DATA: LLM Pricing (costs per 1M tokens in cents)
-- =====================================================
-- Prices as of Feb 2026 (update as needed)
-- margin_multiplier = 1.30 (30% markup)
-- =====================================================

INSERT INTO llm_pricing (provider, model, input_cost_per_1m_cents, output_cost_per_1m_cents, margin_multiplier) VALUES
-- Gemini
('gemini', 'gemini-2.0-flash',       10,   40, 1.30),
('gemini', 'gemini-2.0-flash-lite',    5,   20, 1.30),
('gemini', 'gemini-2.5-pro',         125,  500, 1.30),
('gemini', 'gemini-2.5-flash',        15,   60, 1.30),

-- OpenAI
('openai', 'gpt-4o',                250, 1000, 1.30),
('openai', 'gpt-4o-mini',            15,   60, 1.30),
('openai', 'gpt-4.1',               200,  800, 1.30),
('openai', 'gpt-4.1-mini',           40,  160, 1.30),
('openai', 'gpt-4.1-nano',           10,   40, 1.30),
('openai', 'o3-mini',               110,  440, 1.30),

-- Anthropic
('anthropic', 'claude-sonnet-4-20250514',  300, 1500, 1.30),
('anthropic', 'claude-haiku-4-5-20251001',  80,  400, 1.30),
('anthropic', 'claude-3-5-sonnet-20241022', 300, 1500, 1.30),

-- Ollama (free - local inference)
('ollama', 'llama3',     0, 0, 1.00),
('ollama', 'mistral',    0, 0, 1.00),
('ollama', 'codellama',  0, 0, 1.00),
('ollama', 'phi3',       0, 0, 1.00)
ON DUPLICATE KEY UPDATE
    input_cost_per_1m_cents = VALUES(input_cost_per_1m_cents),
    output_cost_per_1m_cents = VALUES(output_cost_per_1m_cents);
