-- =====================================================
-- Migration: 002_add_audit_logs_status
-- =====================================================
-- Description: Add status column to activity_logs table
--              for tracking success/failure of actions
--
-- Created: 2024-12-12
-- Author: AI Notebook Team
--
-- Run this migration:
--   mysql -u root -p ainotebook < scripts/migrations/002_add_audit_logs_status.sql
--
-- Rollback:
--   ALTER TABLE activity_logs DROP COLUMN status;
-- =====================================================

USE ainotebook;

-- Add status column if it doesn't exist
-- Using a procedure to make this idempotent
DELIMITER //

CREATE PROCEDURE add_status_column_if_not_exists()
BEGIN
    DECLARE column_exists INT DEFAULT 0;

    SELECT COUNT(*) INTO column_exists
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = 'ainotebook'
      AND TABLE_NAME = 'activity_logs'
      AND COLUMN_NAME = 'status';

    IF column_exists = 0 THEN
        ALTER TABLE activity_logs
        ADD COLUMN status ENUM('success', 'failed', 'denied')
        NOT NULL DEFAULT 'success'
        AFTER user_agent;

        -- Add index for filtering by status
        CREATE INDEX idx_activity_status ON activity_logs(status);

        SELECT 'Column status added successfully' AS result;
    ELSE
        SELECT 'Column status already exists, skipping' AS result;
    END IF;
END //

DELIMITER ;

-- Execute the procedure
CALL add_status_column_if_not_exists();

-- Clean up the procedure
DROP PROCEDURE IF EXISTS add_status_column_if_not_exists;

-- Verify the change
DESCRIBE activity_logs;
