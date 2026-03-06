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
    llm_provider ENUM('openai_compatible', 'openai', 'anthropic', 'gemini') DEFAULT 'gemini',
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
-- Multiple keys per provider per user (max 5), one active at a time
-- =====================================================
CREATE TABLE IF NOT EXISTS user_api_keys (
    id CHAR(36) NOT NULL,

    user_id CHAR(36) NOT NULL,
    provider ENUM('openai', 'anthropic', 'gemini', 'openai_compatible') NOT NULL,
    label VARCHAR(100) NULL,

    api_key_encrypted TEXT NOT NULL,
    api_key_hint VARCHAR(20) NOT NULL,

    model_override VARCHAR(100) NULL,
    base_url VARCHAR(500) NULL,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_validated BOOLEAN NOT NULL DEFAULT FALSE,
    last_validated_at TIMESTAMP NULL,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_api_keys_user (user_id),
    INDEX idx_user_api_keys_user_provider (user_id, provider)
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
-- TABLE: llm_models
-- =====================================================
-- Unified model registry: identity, capabilities, and pricing
-- =====================================================
CREATE TABLE IF NOT EXISTS llm_models (
    id INT NOT NULL AUTO_INCREMENT,

    provider VARCHAR(50) NOT NULL,
    model_id VARCHAR(100) NOT NULL,
    display_name VARCHAR(150) NOT NULL,

    -- Capabilities
    context_window INT NULL,
    max_output_tokens INT NULL,
    supports_vision TINYINT(1) NOT NULL DEFAULT 0,
    supports_function_calling TINYINT(1) NOT NULL DEFAULT 0,
    supports_streaming TINYINT(1) NOT NULL DEFAULT 1,

    -- Pricing (cents per 1M tokens)
    input_cost_per_1m_cents INT NOT NULL DEFAULT 0,
    output_cost_per_1m_cents INT NOT NULL DEFAULT 0,
    margin_multiplier DECIMAL(3,2) NOT NULL DEFAULT 1.30,

    -- Status
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    is_custom TINYINT(1) NOT NULL DEFAULT 0,
    sort_order INT NOT NULL DEFAULT 0,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    UNIQUE KEY uk_llm_models_provider_model (provider, model_id),
    INDEX idx_llm_models_active (is_active),
    INDEX idx_llm_models_provider (provider)
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


-- =====================================================
-- 14. PLATFORM API KEYS (encrypted LLM provider keys)
-- =====================================================
CREATE TABLE IF NOT EXISTS platform_api_keys (
    id CHAR(36) NOT NULL,

    provider ENUM('openai','anthropic','gemini','openai_compatible') NOT NULL,
    label VARCHAR(100) NOT NULL,

    api_key_encrypted TEXT NOT NULL,
    api_key_hint VARCHAR(20) NOT NULL,
    auth_type ENUM('api_key','oauth_token') NOT NULL DEFAULT 'api_key',
    model_name VARCHAR(100) NULL,
    base_url VARCHAR(500) NULL,

    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    user_visible BOOLEAN NOT NULL DEFAULT TRUE,
    priority INT NOT NULL DEFAULT 0,

    created_by CHAR(36) NULL,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_platform_keys_provider_active (provider, is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =====================================================
-- 15. SYSTEM PROMPTS (admin-editable LLM system prompts)
-- =====================================================
CREATE TABLE IF NOT EXISTS system_prompts (
    id CHAR(36) NOT NULL,

    prompt_type ENUM('chat_panel','ai_cell') NOT NULL,
    label VARCHAR(100) NOT NULL,
    content MEDIUMTEXT NOT NULL,
    mode_name VARCHAR(50) NULL,
    tools JSON NULL,

    is_active BOOLEAN NOT NULL DEFAULT FALSE,

    created_by CHAR(36) NULL,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL DEFAULT NULL,

    PRIMARY KEY (id),
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_system_prompts_type_active (prompt_type, is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =====================================================
-- 16. PASSWORD RESET TOKENS
-- =====================================================
-- SHA-256 hashed tokens for self-service password reset
-- Raw token only sent via email; 10-minute expiry, single-use
-- =====================================================
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id CHAR(36) NOT NULL,

    user_id CHAR(36) NOT NULL,
    token_hash VARCHAR(64) NOT NULL,

    expires_at TIMESTAMP NOT NULL,
    is_used BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY uk_prt_token_hash (token_hash),
    INDEX idx_prt_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =====================================================
-- 17. AI CELL TOOL CATALOG (available tools for AI cell modes)
-- =====================================================
-- Master list of tools that can be assigned to AI Cell modes.
-- Playground has the actual implementations; this table controls
-- which tools are visible/assignable in the admin UI.
-- Admin manually adds new tools here when playground adds them.
-- =====================================================
CREATE TABLE IF NOT EXISTS ai_cell_tool_catalog (
    name VARCHAR(100) NOT NULL,
    category VARCHAR(50) NOT NULL,
    description VARCHAR(255) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (name),
    INDEX idx_tool_catalog_category (category),
    INDEX idx_tool_catalog_active (is_active)
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
-- Default model registry with capabilities and pricing
-- margin_multiplier = 1.30 (30% markup on platform keys)
-- =====================================================

INSERT INTO llm_models (provider, model_id, display_name, context_window, max_output_tokens, supports_vision, supports_function_calling, input_cost_per_1m_cents, output_cost_per_1m_cents, margin_multiplier, sort_order) VALUES
-- Gemini
('gemini', 'gemini-2.0-flash',      'Gemini 2.0 Flash',      1048576,  8192, TRUE,  TRUE,   10,   40, 1.30, 1),
('gemini', 'gemini-2.0-flash-lite', 'Gemini 2.0 Flash Lite', 1048576,  8192, TRUE,  TRUE,    5,   20, 1.30, 2),
('gemini', 'gemini-2.5-pro',        'Gemini 2.5 Pro',        1048576, 65536, TRUE,  TRUE,  125,  500, 1.30, 3),
('gemini', 'gemini-2.5-flash',      'Gemini 2.5 Flash',      1048576, 65536, TRUE,  TRUE,   15,   60, 1.30, 4),
-- OpenAI
('openai', 'gpt-4o',       'GPT-4o',       128000,  16384, TRUE,  TRUE,  250, 1000, 1.30, 1),
('openai', 'gpt-4o-mini',  'GPT-4o Mini',  128000,  16384, TRUE,  TRUE,   15,   60, 1.30, 2),
('openai', 'gpt-4.1',      'GPT-4.1',     1047576,  32768, TRUE,  TRUE,  200,  800, 1.30, 3),
('openai', 'gpt-4.1-mini', 'GPT-4.1 Mini',1047576,  32768, TRUE,  TRUE,   40,  160, 1.30, 4),
('openai', 'gpt-4.1-nano', 'GPT-4.1 Nano',1047576,  32768, FALSE, TRUE,   10,   40, 1.30, 5),
('openai', 'o3-mini',      'o3-mini',      200000, 100000, FALSE, TRUE,  110,  440, 1.30, 6),
-- Anthropic
('anthropic', 'claude-sonnet-4-20250514',  'Claude Sonnet 4',   200000, 16000, TRUE, TRUE, 300, 1500, 1.30, 1),
('anthropic', 'claude-haiku-4-5-20251001', 'Claude Haiku 4.5',  200000,  8192, TRUE, TRUE,  80,  400, 1.30, 2),
('anthropic', 'claude-3-5-sonnet-20241022','Claude 3.5 Sonnet',  200000,  8192, TRUE, TRUE, 300, 1500, 1.30, 3),
-- OpenAI Compatible (free - local inference / custom endpoints)
('openai_compatible', 'custom', 'Custom Model', NULL, NULL, FALSE, FALSE, 0, 0, 1.00, 99)
ON DUPLICATE KEY UPDATE
    display_name = VALUES(display_name),
    context_window = VALUES(context_window),
    max_output_tokens = VALUES(max_output_tokens),
    supports_vision = VALUES(supports_vision),
    supports_function_calling = VALUES(supports_function_calling),
    input_cost_per_1m_cents = VALUES(input_cost_per_1m_cents),
    output_cost_per_1m_cents = VALUES(output_cost_per_1m_cents);


-- =====================================================
-- SEED DATA: AI Cell Tool Catalog
-- =====================================================
-- All 19 tools currently implemented in the playground.
-- Add new rows here when new tools are added to playground code.
-- =====================================================

INSERT INTO ai_cell_tool_catalog (name, category, description, is_active) VALUES
-- Runtime Inspection
('runtime_list_variables',  'Runtime Inspection', 'List all variables in the running kernel',    TRUE),
('runtime_get_variable',    'Runtime Inspection', 'Get the value of a specific variable',        TRUE),
('runtime_get_dataframe',   'Runtime Inspection', 'Get DataFrame info and preview',              TRUE),
('runtime_list_functions',  'Runtime Inspection', 'List user-defined functions in the kernel',    TRUE),
('runtime_list_imports',    'Runtime Inspection', 'List imported modules in the kernel',          TRUE),
('runtime_kernel_status',   'Runtime Inspection', 'Get kernel status and resource usage',         TRUE),
('runtime_get_last_error',  'Runtime Inspection', 'Get the last error/exception from the kernel', TRUE),
-- Notebook
('get_notebook_overview',   'Notebook',           'Get overview of all cells in the notebook',    TRUE),
('get_cell_content',        'Notebook',           'Get the source content of a specific cell',    TRUE),
-- Sandbox
('sandbox_execute',         'Sandbox',            'Execute code in an isolated sandbox kernel',   TRUE),
('sandbox_reset',           'Sandbox',            'Reset the sandbox kernel to a clean state',    TRUE),
('sandbox_pip_install',     'Sandbox',            'Install packages in the sandbox environment',  TRUE),
('sandbox_sync_from_main',  'Sandbox',            'Sync variables from main kernel to sandbox',   TRUE),
('sandbox_status',          'Sandbox',            'Get sandbox kernel status',                    TRUE),
-- File Utilities
('list_files',              'File Utilities',     'List files matching a glob pattern',           TRUE),
('search_files',            'File Utilities',     'Search file contents with regex',              TRUE),
('read_text_file',          'File Utilities',     'Read contents of a text file',                 TRUE),
('get_workspace_context',   'File Utilities',     'Get workspace structure and file contents',    TRUE),
-- Web
('web_fetch',               'Web',                'Fetch content from a URL',                     TRUE)
ON DUPLICATE KEY UPDATE
    category = VALUES(category),
    description = VALUES(description);
