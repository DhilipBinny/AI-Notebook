-- Migration 009: Add password_reset_tokens table
-- Rollback: DROP TABLE IF EXISTS password_reset_tokens;

USE ainotebook;

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
