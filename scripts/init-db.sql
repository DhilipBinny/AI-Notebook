-- =====================================================
-- AI Notebook Platform - Database Schema
-- =====================================================
-- Database: MySQL 8.0
-- Charset: utf8mb4 (full Unicode support)
--
-- Run this script to initialize the database:
--   mysql -u root -p ainotebook < scripts/init-db.sql
--
-- Or it will run automatically when MySQL container starts
--
-- Last updated: 2026-02-21 (includes business logic tables)
-- =====================================================

USE ainotebook;

-- Disable FK checks during creation (handles table ordering)
SET FOREIGN_KEY_CHECKS = 0;


-- =====================================================
-- TABLE: users
-- =====================================================
-- Stores user accounts and authentication info
-- Supports both local (email/password) and OAuth login
-- =====================================================
CREATE TABLE IF NOT EXISTS users (
    id CHAR(36) NOT NULL,

    -- Basic info
    email VARCHAR(255) NOT NULL,
    name VARCHAR(255) NULL,
    avatar_url VARCHAR(500) NULL,

    -- Local auth (NULL if OAuth only)
    password_hash VARCHAR(255) NULL,

    -- OAuth info (NULL if local only)
    oauth_provider ENUM('local', 'google', 'github') DEFAULT 'local',
    oauth_id VARCHAR(255) NULL,

    -- Account settings
    max_projects INT NOT NULL DEFAULT 5,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    is_admin BOOLEAN NOT NULL DEFAULT FALSE,

    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP NULL,

    PRIMARY KEY (id),
    UNIQUE KEY uk_users_email (email),
    UNIQUE KEY uk_users_oauth (oauth_provider, oauth_id),
    INDEX idx_users_active (is_active),
    INDEX idx_users_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =====================================================
-- TABLE: workspaces
-- =====================================================
-- Organizes projects into groups/folders
-- =====================================================
CREATE TABLE IF NOT EXISTS workspaces (
    id CHAR(36) NOT NULL,

    user_id CHAR(36) NOT NULL,

    name VARCHAR(255) NOT NULL,
    description TEXT NULL,

    -- Visual customization
    color VARCHAR(7) NOT NULL DEFAULT '#3B82F6',
    icon VARCHAR(50) NULL DEFAULT 'folder',

    -- State
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order VARCHAR(50) NOT NULL DEFAULT '0',

    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL,

    PRIMARY KEY (id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_workspaces_user (user_id),
    INDEX idx_workspaces_deleted (is_deleted)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =====================================================
-- TABLE: projects
-- =====================================================
-- Stores notebook projects
-- Each project has one .ipynb file stored in MinIO/S3
-- =====================================================
CREATE TABLE IF NOT EXISTS projects (
    id CHAR(36) NOT NULL,

    user_id CHAR(36) NOT NULL,
    workspace_id CHAR(36) NULL,

    name VARCHAR(255) NOT NULL,
    description TEXT NULL,

    -- Storage location in MinIO: {mm-yyyy}/{project_id}/notebook.ipynb
    storage_path VARCHAR(500) NOT NULL,
    storage_month VARCHAR(7) NOT NULL,

    -- LLM settings
    llm_provider ENUM('ollama', 'openai', 'anthropic', 'gemini') DEFAULT 'gemini',
    llm_model VARCHAR(100) NULL,

    -- State
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,

    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_opened_at TIMESTAMP NULL,
    deleted_at TIMESTAMP NULL,

    PRIMARY KEY (id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE SET NULL,
    INDEX idx_projects_user (user_id),
    INDEX idx_projects_workspace (workspace_id),
    INDEX idx_projects_user_active (user_id, is_archived),
    INDEX idx_projects_updated (updated_at),
    INDEX idx_projects_deleted (deleted_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =====================================================
-- TABLE: playgrounds
-- =====================================================
-- Tracks active container instances
-- One playground per USER (user-scoped container model)
-- project_id = currently active project in the container
-- =====================================================
CREATE TABLE IF NOT EXISTS playgrounds (
    id CHAR(36) NOT NULL,

    -- User reference (unique - one container per user)
    user_id CHAR(36) NOT NULL,

    -- Active project (nullable - container can exist without a project)
    project_id CHAR(36) NULL,

    -- Container info
    container_id VARCHAR(255) NOT NULL,
    container_name VARCHAR(255) NOT NULL,     -- playground-{user_id[:8]}
    internal_url VARCHAR(500) NOT NULL,
    internal_secret VARCHAR(255) NOT NULL,

    -- State
    status ENUM('starting', 'running', 'stopping', 'stopped', 'error') NOT NULL DEFAULT 'starting',
    error_message TEXT NULL,

    -- Resource limits
    memory_limit_mb INT NOT NULL DEFAULT 2048,
    cpu_limit DECIMAL(3,2) NOT NULL DEFAULT 1.00,

    -- Timestamps
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_activity_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    stopped_at TIMESTAMP NULL,

    PRIMARY KEY (id),
    UNIQUE KEY uk_playgrounds_user (user_id),
    UNIQUE KEY uk_playgrounds_container (container_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL,
    INDEX idx_playgrounds_project (project_id),
    INDEX idx_playgrounds_status (status),
    INDEX idx_playgrounds_activity (last_activity_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =====================================================
-- TABLE: sessions
-- =====================================================
-- Stores refresh tokens for JWT authentication
-- =====================================================
CREATE TABLE IF NOT EXISTS sessions (
    id CHAR(36) NOT NULL,

    user_id CHAR(36) NOT NULL,

    refresh_token_hash VARCHAR(255) NOT NULL,

    -- Device/client info
    user_agent VARCHAR(500) NULL,
    ip_address VARCHAR(45) NULL,

    -- Validity
    expires_at TIMESTAMP NOT NULL,
    is_revoked BOOLEAN NOT NULL DEFAULT FALSE,

    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP NULL,

    PRIMARY KEY (id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_sessions_user (user_id),
    INDEX idx_sessions_expires (expires_at),
    INDEX idx_sessions_token (refresh_token_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =====================================================
-- TABLE: activity_logs
-- =====================================================
-- Tracks user activity for security auditing
-- =====================================================
CREATE TABLE IF NOT EXISTS activity_logs (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,

    user_id CHAR(36) NULL,

    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50) NULL,
    resource_id CHAR(36) NULL,

    metadata JSON NULL,
    ip_address VARCHAR(45) NULL,
    user_agent VARCHAR(500) NULL,

    status ENUM('success', 'failed', 'denied') NOT NULL DEFAULT 'success',

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    INDEX idx_activity_user (user_id),
    INDEX idx_activity_action (action),
    INDEX idx_activity_resource (resource_type, resource_id),
    INDEX idx_activity_created (created_at),
    INDEX idx_activity_status (status),
    INDEX idx_activity_user_action (user_id, action, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =====================================================
-- TABLE: invitations
-- =====================================================
-- Invite codes for controlled user onboarding
-- =====================================================
CREATE TABLE IF NOT EXISTS invitations (
    id CHAR(36) NOT NULL,

    code VARCHAR(64) NOT NULL,
    email VARCHAR(255) NULL,

    max_uses INT NOT NULL DEFAULT 1,
    used_count INT NOT NULL DEFAULT 0,

    created_by CHAR(36) NOT NULL,

    expires_at TIMESTAMP NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    note VARCHAR(500) NULL,

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
-- TABLE: user_api_keys
-- =====================================================
-- User-owned LLM API keys (Fernet encrypted)
-- One key per provider per user
-- =====================================================
CREATE TABLE IF NOT EXISTS user_api_keys (
    id CHAR(36) NOT NULL,

    user_id CHAR(36) NOT NULL,
    provider ENUM('openai', 'anthropic', 'gemini', 'ollama') NOT NULL,

    api_key_encrypted TEXT NOT NULL,
    api_key_hint VARCHAR(20) NOT NULL,

    model_override VARCHAR(100) NULL,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_validated BOOLEAN NOT NULL DEFAULT FALSE,
    last_validated_at TIMESTAMP NULL,

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
-- Credit balance per user (1:1 with users)
-- balance_cents: 1000 = $10.00
-- =====================================================
CREATE TABLE IF NOT EXISTS user_credits (
    user_id CHAR(36) NOT NULL,

    balance_cents INT NOT NULL DEFAULT 1000,
    total_deposited_cents INT NOT NULL DEFAULT 1000,
    total_consumed_cents INT NOT NULL DEFAULT 0,

    last_charged_at TIMESTAMP NULL,

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

    input_cost_per_1m_cents INT NOT NULL,
    output_cost_per_1m_cents INT NOT NULL,

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

    provider VARCHAR(50) NOT NULL,
    model VARCHAR(100) NOT NULL,
    request_type ENUM('chat', 'ai_cell', 'summarize') NOT NULL DEFAULT 'chat',

    input_tokens INT NOT NULL DEFAULT 0,
    output_tokens INT NOT NULL DEFAULT 0,
    cached_tokens INT NOT NULL DEFAULT 0,

    cost_cents INT NOT NULL DEFAULT 0,
    raw_cost_cents INT NOT NULL DEFAULT 0,

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

    storage_path VARCHAR(500) NOT NULL,

    thumbnail_url VARCHAR(500) NULL,
    difficulty_level ENUM('beginner', 'intermediate', 'advanced') NOT NULL DEFAULT 'beginner',
    estimated_minutes INT NULL,
    tags JSON NULL,

    is_public BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order INT NOT NULL DEFAULT 0,

    created_by CHAR(36) NULL,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_templates_public (is_public),
    INDEX idx_templates_category (category),
    INDEX idx_templates_sort (sort_order),
    INDEX idx_templates_created_by (created_by)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- Re-enable FK checks
SET FOREIGN_KEY_CHECKS = 1;


-- =====================================================
-- STORED PROCEDURES
-- =====================================================

DELIMITER //
CREATE PROCEDURE IF NOT EXISTS cleanup_expired_sessions()
BEGIN
    DELETE FROM sessions
    WHERE expires_at < NOW()
       OR is_revoked = TRUE;
END //
DELIMITER ;

DELIMITER //
CREATE PROCEDURE IF NOT EXISTS cleanup_stale_playgrounds()
BEGIN
    UPDATE playgrounds
    SET status = 'stopped',
        stopped_at = NOW()
    WHERE status = 'running'
      AND last_activity_at < DATE_SUB(NOW(), INTERVAL 4 HOUR);
END //
DELIMITER ;


-- =====================================================
-- SEED DATA: LLM Pricing
-- =====================================================
-- Default pricing for all supported models
-- margin_multiplier = 1.30 (30% markup on platform keys)
-- Ollama = free (local inference)
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
