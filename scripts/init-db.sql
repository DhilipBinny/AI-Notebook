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
-- =====================================================

-- Use the database
USE ainotebook;

-- =====================================================
-- TABLE: users
-- =====================================================
-- Stores user accounts and authentication info
-- Supports both local (email/password) and OAuth login
-- =====================================================
CREATE TABLE IF NOT EXISTS users (
    -- Primary key (UUID v4)
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
    max_projects INT NOT NULL DEFAULT 5,  -- Maximum notebooks per user
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,

    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP NULL,

    -- Constraints
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
-- Each user can have multiple workspaces
-- =====================================================
CREATE TABLE IF NOT EXISTS workspaces (
    -- Primary key (UUID v4)
    id CHAR(36) NOT NULL,

    -- Owner reference
    user_id CHAR(36) NOT NULL,

    -- Workspace info
    name VARCHAR(255) NOT NULL,
    description TEXT NULL,

    -- Visual customization
    color VARCHAR(7) NOT NULL DEFAULT '#3B82F6',  -- Hex color (default: blue)
    icon VARCHAR(50) NULL DEFAULT 'folder',        -- Icon name

    -- State
    is_default BOOLEAN NOT NULL DEFAULT FALSE,    -- One default per user
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,    -- Soft delete flag
    sort_order VARCHAR(50) NOT NULL DEFAULT '0',  -- Display order

    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL,                    -- Soft delete timestamp

    -- Constraints
    PRIMARY KEY (id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_workspaces_user (user_id),
    INDEX idx_workspaces_deleted (is_deleted)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =====================================================
-- TABLE: projects
-- =====================================================
-- Stores notebook projects
-- Each project has one .ipynb file stored in MinIO
-- Projects can optionally belong to a workspace
-- =====================================================
CREATE TABLE IF NOT EXISTS projects (
    -- Primary key (UUID v4)
    id CHAR(36) NOT NULL,

    -- Owner reference
    user_id CHAR(36) NOT NULL,

    -- Workspace reference (optional - for grouping)
    workspace_id CHAR(36) NULL,

    -- Project info
    name VARCHAR(255) NOT NULL,
    description TEXT NULL,

    -- Storage location in MinIO
    -- Format: {mm-yyyy}/{project_id}/notebook.ipynb
    storage_path VARCHAR(500) NOT NULL,
    storage_month VARCHAR(7) NOT NULL,  -- mm-yyyy format, for folder organization

    -- Settings
    llm_provider ENUM('ollama', 'openai', 'anthropic', 'gemini') DEFAULT 'gemini',
    llm_model VARCHAR(100) NULL,

    -- State
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,

    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_opened_at TIMESTAMP NULL,
    deleted_at TIMESTAMP NULL,  -- Soft delete timestamp

    -- Constraints
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
-- One playground per project at a time
-- =====================================================
CREATE TABLE IF NOT EXISTS playgrounds (
    -- Primary key (UUID v4)
    id CHAR(36) NOT NULL,

    -- Project reference (unique - only one active playground per project)
    project_id CHAR(36) NOT NULL,

    -- Container info
    container_id VARCHAR(255) NOT NULL,      -- Docker container ID
    container_name VARCHAR(255) NOT NULL,    -- For routing: playground-{short_id}
    internal_url VARCHAR(500) NOT NULL,      -- http://playground-xxx:8888
    internal_secret VARCHAR(255) NOT NULL,   -- Auth token for internal requests

    -- State
    status ENUM('starting', 'running', 'stopping', 'stopped', 'error') NOT NULL DEFAULT 'starting',
    error_message TEXT NULL,

    -- Resource tracking
    memory_limit_mb INT NOT NULL DEFAULT 2048,
    cpu_limit DECIMAL(3,2) NOT NULL DEFAULT 1.00,

    -- Timestamps
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_activity_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    stopped_at TIMESTAMP NULL,

    -- Constraints
    PRIMARY KEY (id),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    UNIQUE KEY uk_playgrounds_project (project_id),  -- Only one active per project
    UNIQUE KEY uk_playgrounds_container (container_id),
    INDEX idx_playgrounds_status (status),
    INDEX idx_playgrounds_activity (last_activity_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =====================================================
-- TABLE: sessions
-- =====================================================
-- Stores refresh tokens for JWT authentication
-- Allows multiple sessions per user (multiple devices)
-- =====================================================
CREATE TABLE IF NOT EXISTS sessions (
    -- Primary key (UUID v4)
    id CHAR(36) NOT NULL,

    -- User reference
    user_id CHAR(36) NOT NULL,

    -- Token info (store hash, not the actual token)
    refresh_token_hash VARCHAR(255) NOT NULL,

    -- Device/client info
    user_agent VARCHAR(500) NULL,
    ip_address VARCHAR(45) NULL,  -- IPv6 max length

    -- Validity
    expires_at TIMESTAMP NOT NULL,
    is_revoked BOOLEAN NOT NULL DEFAULT FALSE,

    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP NULL,

    -- Constraints
    PRIMARY KEY (id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_sessions_user (user_id),
    INDEX idx_sessions_expires (expires_at),
    INDEX idx_sessions_token (refresh_token_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =====================================================
-- TABLE: activity_logs (optional - for auditing)
-- =====================================================
-- Tracks user activity for auditing and analytics
-- =====================================================
CREATE TABLE IF NOT EXISTS activity_logs (
    -- Primary key (auto-increment for performance)
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,

    -- User reference (NULL for system events)
    user_id CHAR(36) NULL,

    -- Activity info
    action VARCHAR(100) NOT NULL,  -- e.g., 'project.create', 'playground.start'
    resource_type VARCHAR(50) NULL,  -- e.g., 'project', 'playground'
    resource_id CHAR(36) NULL,

    -- Additional context
    metadata JSON NULL,
    ip_address VARCHAR(45) NULL,
    user_agent VARCHAR(500) NULL,

    -- Timestamp
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    PRIMARY KEY (id),
    INDEX idx_activity_user (user_id),
    INDEX idx_activity_action (action),
    INDEX idx_activity_resource (resource_type, resource_id),
    INDEX idx_activity_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =====================================================
-- STORED PROCEDURES
-- =====================================================

-- Procedure to clean up expired sessions
DELIMITER //
CREATE PROCEDURE IF NOT EXISTS cleanup_expired_sessions()
BEGIN
    DELETE FROM sessions
    WHERE expires_at < NOW()
       OR is_revoked = TRUE;
END //
DELIMITER ;

-- Procedure to clean up stale playgrounds (not updated in 4+ hours)
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
-- SCHEDULED EVENTS (optional - requires event_scheduler ON)
-- =====================================================
-- Enable with: SET GLOBAL event_scheduler = ON;

-- Clean expired sessions every hour
-- CREATE EVENT IF NOT EXISTS evt_cleanup_sessions
-- ON SCHEDULE EVERY 1 HOUR
-- DO CALL cleanup_expired_sessions();

-- Clean stale playgrounds every 15 minutes
-- CREATE EVENT IF NOT EXISTS evt_cleanup_playgrounds
-- ON SCHEDULE EVERY 15 MINUTE
-- DO CALL cleanup_stale_playgrounds();


-- =====================================================
-- INITIAL DATA (Optional - for development)
-- =====================================================

-- Create a test user (password: testpassword123)
-- Password hash is bcrypt of 'testpassword123'
-- INSERT INTO users (id, email, name, password_hash, is_verified)
-- VALUES (
--     UUID(),
--     'test@example.com',
--     'Test User',
--     '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.RVOm.1VbW/1234',  -- Replace with real hash
--     TRUE
-- );
