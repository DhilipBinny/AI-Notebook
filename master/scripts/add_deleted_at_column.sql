-- Add deleted_at column for soft delete functionality
-- Run this against the MySQL database

ALTER TABLE projects ADD COLUMN deleted_at DATETIME NULL;
CREATE INDEX ix_projects_deleted_at ON projects (deleted_at);
