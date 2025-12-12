# Database Schema Documentation

## Overview

The AI Notebook Platform uses **MySQL 8.0** as its primary database for user, project, and session management.

| Property | Value |
|----------|-------|
| Database | MySQL 8.0 |
| Character Set | utf8mb4 (full Unicode support) |
| Collation | utf8mb4_unicode_ci |
| Primary Keys | UUID v4 (CHAR(36)) |

> **Note:** Chat history and notebook files are stored in **MinIO/S3**, not in the database.

---

## Entity Relationship Diagram

```
┌─────────────────────┐
│       users         │
├─────────────────────┤
│ id (PK)             │
│ email (UNIQUE)      │
│ name                │
│ avatar_url          │
│ password_hash       │
│ oauth_provider      │
│ oauth_id            │
│ max_projects        │
│ is_active           │
│ is_verified         │
│ created_at          │
│ updated_at          │
│ last_login_at       │
└─────────┬───────────┘
          │
          │ 1:N                         1:N
          ├──────────────────────────────────┐
          │                                  │
          ▼                                  ▼
┌─────────────────────┐       ┌─────────────────────┐
│     workspaces      │       │      sessions       │
├─────────────────────┤       ├─────────────────────┤
│ id (PK)             │       │ id (PK)             │
│ user_id (FK)        │       │ user_id (FK)        │
│ name                │       │ refresh_token_hash  │
│ description         │       │ user_agent          │
│ color               │       │ ip_address          │
│ icon                │       │ expires_at          │
│ is_default          │       │ is_revoked          │
│ is_deleted          │       │ created_at          │
│ sort_order          │       │ last_used_at        │
│ created_at          │       └─────────────────────┘
│ updated_at          │
│ deleted_at          │
└─────────┬───────────┘
          │
          │ 1:N (optional)
          ▼
┌─────────────────────┐       ┌─────────────────────┐
│      projects       │       │     playgrounds     │
├─────────────────────┤       ├─────────────────────┤
│ id (PK)             │──────<│ id (PK)             │
│ user_id (FK)        │  1:1  │ project_id (FK,UQ)  │
│ workspace_id (FK)   │       │ container_id (UQ)   │
│ name                │       │ container_name      │
│ description         │       │ internal_url        │
│ storage_path        │       │ internal_secret     │
│ storage_month       │       │ status              │
│ llm_provider *      │       │ error_message       │
│ llm_model *         │       │ memory_limit_mb     │
│ is_archived         │       │ cpu_limit           │
│ deleted_at          │       │ started_at          │
│ created_at          │       │ last_activity_at    │
│ updated_at          │       │ stopped_at          │
│ last_opened_at      │       └─────────────────────┘
└─────────────────────┘

┌─────────────────────┐
│    activity_logs    │
├─────────────────────┤
│ id (PK, AUTO_INCR)  │
│ user_id (FK)        │
│ action              │
│ resource_type       │
│ resource_id         │
│ metadata (JSON)     │
│ ip_address          │
│ user_agent          │
│ status              │
│ created_at          │
└─────────────────────┘

* llm_provider and llm_model are deprecated (kept for backward compatibility)
```

---

## Tables

### 1. `users`

Stores user accounts. Supports local (email/password) and OAuth authentication.

| Column | Type | Null | Key | Default | Description |
|--------|------|------|-----|---------|-------------|
| `id` | CHAR(36) | NO | PK | - | UUID v4 |
| `email` | VARCHAR(255) | NO | UQ | - | User's email |
| `name` | VARCHAR(255) | YES | - | NULL | Display name |
| `avatar_url` | VARCHAR(500) | YES | - | NULL | Profile picture URL |
| `password_hash` | VARCHAR(255) | YES | - | NULL | Bcrypt hash (NULL for OAuth) |
| `oauth_provider` | ENUM | YES | - | 'local' | 'local', 'google', 'github' |
| `oauth_id` | VARCHAR(255) | YES | - | NULL | OAuth provider user ID |
| `max_projects` | INT | NO | - | 5 | Max notebooks allowed |
| `is_active` | BOOLEAN | NO | IDX | TRUE | Account status |
| `is_verified` | BOOLEAN | NO | - | FALSE | Email verified |
| `created_at` | TIMESTAMP | NO | IDX | NOW() | Creation time |
| `updated_at` | TIMESTAMP | NO | - | NOW() | Auto-updated |
| `last_login_at` | TIMESTAMP | YES | - | NULL | Last login time |

**Indexes:**

| Name | Type | Columns | Description |
|------|------|---------|-------------|
| `PRIMARY` | PK | id | Primary key |
| `uk_users_email` | UNIQUE | email | Unique email constraint |
| `uk_users_oauth` | UNIQUE | (oauth_provider, oauth_id) | Unique OAuth identity |
| `idx_users_active` | INDEX | is_active | Filter active users |
| `idx_users_created` | INDEX | created_at | Sort by creation date |

---

### 2. `workspaces`

Organizes projects/notebooks into groups for better organization.

| Column | Type | Null | Key | Default | Description |
|--------|------|------|-----|---------|-------------|
| `id` | CHAR(36) | NO | PK | - | UUID v4 |
| `user_id` | CHAR(36) | NO | FK,IDX | - | Owner reference |
| `name` | VARCHAR(255) | NO | - | - | Workspace name |
| `description` | TEXT | YES | - | NULL | Description |
| `color` | VARCHAR(7) | NO | - | '#3B82F6' | Hex color code |
| `icon` | VARCHAR(50) | YES | - | 'folder' | Icon identifier |
| `is_default` | BOOLEAN | NO | - | FALSE | Default workspace flag |
| `is_deleted` | BOOLEAN | NO | IDX | FALSE | Soft delete flag |
| `sort_order` | VARCHAR(50) | NO | - | '0' | Display order |
| `created_at` | TIMESTAMP | NO | - | NOW() | Creation time |
| `updated_at` | TIMESTAMP | NO | - | NOW() | Auto-updated |
| `deleted_at` | DATETIME | YES | - | NULL | Soft delete timestamp |

**Indexes:**

| Name | Type | Columns | Description |
|------|------|---------|-------------|
| `PRIMARY` | PK | id | Primary key |
| `idx_workspaces_user` | INDEX | user_id | Filter by owner |
| `idx_workspaces_deleted` | INDEX | is_deleted | Filter active workspaces |

**Notes:**
- Each user can have multiple workspaces
- Projects can optionally belong to a workspace
- When a workspace is deleted, its projects become "uncategorized" (workspace_id = NULL)
- The `color` field stores hex color codes for UI display (e.g., '#3B82F6' for blue)

---

### 3. `projects`

Stores notebook projects. Each project maps to files in MinIO storage.

| Column | Type | Null | Key | Default | Description |
|--------|------|------|-----|---------|-------------|
| `id` | CHAR(36) | NO | PK | - | UUID v4 |
| `user_id` | CHAR(36) | NO | FK,IDX | - | Owner reference |
| `workspace_id` | CHAR(36) | YES | FK,IDX | NULL | Workspace (optional) |
| `name` | VARCHAR(255) | NO | - | - | Project name |
| `description` | TEXT | YES | - | NULL | Description |
| `storage_path` | VARCHAR(500) | NO | - | - | Full MinIO path |
| `storage_month` | VARCHAR(7) | NO | - | - | Folder partition (MM-YYYY) |
| `llm_provider` | ENUM | YES | - | 'gemini' | **Deprecated** |
| `llm_model` | VARCHAR(100) | YES | - | NULL | **Deprecated** |
| `is_archived` | BOOLEAN | NO | IDX | FALSE | Archive flag |
| `deleted_at` | DATETIME | YES | IDX | NULL | Soft delete timestamp |
| `created_at` | TIMESTAMP | NO | - | NOW() | Creation time |
| `updated_at` | TIMESTAMP | NO | IDX | NOW() | Auto-updated |
| `last_opened_at` | TIMESTAMP | YES | - | NULL | Last opened |

**Indexes:**

| Name | Type | Columns | Description |
|------|------|---------|-------------|
| `PRIMARY` | PK | id | Primary key |
| `idx_projects_user` | INDEX | user_id | Filter by owner |
| `idx_projects_workspace` | INDEX | workspace_id | Filter by workspace |
| `idx_projects_user_active` | INDEX | (user_id, is_archived) | User's active projects |
| `idx_projects_updated` | INDEX | updated_at | Sort by update time |
| `ix_projects_deleted_at` | INDEX | deleted_at | Soft delete filtering |

**Storage Structure:**
```
MinIO: notebooks/{storage_month}/{project_id}/
├── notebook.json          # Notebook cells and metadata
└── chats/
    ├── default.json       # Default chat history
    └── {chat_id}.json     # Additional chat sessions
```

**Soft Delete:**
- When `deleted_at` is NULL, project is active
- When `deleted_at` has a timestamp, project is soft-deleted
- All queries filter `WHERE deleted_at IS NULL` by default

---

### 4. `playgrounds`

Tracks active Docker container instances. One playground per project maximum.

| Column | Type | Null | Key | Default | Description |
|--------|------|------|-----|---------|-------------|
| `id` | CHAR(36) | NO | PK | - | UUID v4 |
| `project_id` | CHAR(36) | NO | FK,UQ | - | One per project |
| `container_id` | VARCHAR(255) | NO | UQ | - | Docker container ID |
| `container_name` | VARCHAR(255) | NO | - | - | For nginx routing |
| `internal_url` | VARCHAR(500) | NO | - | - | Internal Docker URL |
| `internal_secret` | VARCHAR(255) | NO | - | - | Auth token |
| `status` | ENUM | NO | IDX | 'starting' | Container state |
| `error_message` | TEXT | YES | - | NULL | Error details |
| `memory_limit_mb` | INT | NO | - | 2048 | Memory limit |
| `cpu_limit` | DECIMAL(3,2) | NO | - | 1.00 | CPU limit |
| `started_at` | TIMESTAMP | NO | - | NOW() | Start time |
| `last_activity_at` | TIMESTAMP | NO | IDX | NOW() | Activity tracking |
| `stopped_at` | TIMESTAMP | YES | - | NULL | Stop time |

**Status Values:**

| Status | Description |
|--------|-------------|
| `starting` | Container being created |
| `running` | Active and healthy |
| `stopping` | Shutdown in progress |
| `stopped` | Terminated normally |
| `error` | Failed state |

**Indexes:**

| Name | Type | Columns | Description |
|------|------|---------|-------------|
| `PRIMARY` | PK | id | Primary key |
| `uk_playgrounds_project` | UNIQUE | project_id | One per project |
| `uk_playgrounds_container` | UNIQUE | container_id | Unique container |
| `idx_playgrounds_status` | INDEX | status | Filter by status |
| `idx_playgrounds_activity` | INDEX | last_activity_at | Cleanup queries |

---

### 5. `sessions`

Stores JWT refresh tokens. Supports multiple sessions per user (devices).

| Column | Type | Null | Key | Default | Description |
|--------|------|------|-----|---------|-------------|
| `id` | CHAR(36) | NO | PK | - | UUID v4 |
| `user_id` | CHAR(36) | NO | FK,IDX | - | Owner |
| `refresh_token_hash` | VARCHAR(255) | NO | IDX | - | Hashed token |
| `user_agent` | VARCHAR(500) | YES | - | NULL | Browser/device |
| `ip_address` | VARCHAR(45) | YES | - | NULL | Client IP (IPv6 ready) |
| `expires_at` | TIMESTAMP | NO | IDX | - | Expiration |
| `is_revoked` | BOOLEAN | NO | - | FALSE | Manually revoked |
| `created_at` | TIMESTAMP | NO | - | NOW() | Creation time |
| `last_used_at` | TIMESTAMP | YES | - | NULL | Last refresh |

**Indexes:**

| Name | Type | Columns | Description |
|------|------|---------|-------------|
| `PRIMARY` | PK | id | Primary key |
| `idx_sessions_user` | INDEX | user_id | User's sessions |
| `idx_sessions_expires` | INDEX | expires_at | Cleanup expired |
| `idx_sessions_token` | INDEX | refresh_token_hash | Token lookup |

---

### 6. `activity_logs`

Audit trail for tracking user actions, authentication events, and system operations.
Critical for security monitoring, debugging, and analytics.

| Column | Type | Null | Key | Default | Description |
|--------|------|------|-----|---------|-------------|
| `id` | BIGINT UNSIGNED | NO | PK | AUTO | Log ID (auto-increment) |
| `user_id` | CHAR(36) | YES | IDX | NULL | Actor (NULL for system/anonymous) |
| `action` | VARCHAR(100) | NO | IDX | - | Action name (see below) |
| `resource_type` | VARCHAR(50) | YES | IDX | NULL | Resource type |
| `resource_id` | CHAR(36) | YES | - | NULL | Resource ID |
| `metadata` | JSON | YES | - | NULL | Action-specific context |
| `ip_address` | VARCHAR(45) | YES | - | NULL | Client IP (IPv4/IPv6) |
| `user_agent` | VARCHAR(500) | YES | - | NULL | Browser/device info |
| `status` | ENUM | NO | IDX | 'success' | Result status |
| `created_at` | TIMESTAMP | NO | IDX | NOW() | Event timestamp |

**Status Values:**

| Status | Description |
|--------|-------------|
| `success` | Action completed successfully |
| `failed` | Action failed (error, invalid input, etc.) |
| `denied` | Action denied (permission, auth failure) |

**Indexes:**

| Name | Type | Columns | Description |
|------|------|---------|-------------|
| `PRIMARY` | PK | id | Primary key |
| `idx_activity_user` | INDEX | user_id | Filter by user |
| `idx_activity_action` | INDEX | action | Filter by action type |
| `idx_activity_resource` | INDEX | (resource_type, resource_id) | Find resource history |
| `idx_activity_created` | INDEX | created_at | Time-based queries |
| `idx_activity_status` | INDEX | status | Filter failures/denials |
| `idx_activity_user_action` | INDEX | (user_id, action, created_at) | User audit queries |

**Authentication Actions (Priority: High):**

| Action | Description | Status Examples |
|--------|-------------|-----------------|
| `auth.login` | Email/password login | success, failed (bad password), denied |
| `auth.login_oauth` | OAuth login (Google, etc.) | success, failed |
| `auth.logout` | User logout | success |
| `auth.register` | New account creation | success, failed |
| `auth.token_refresh` | JWT token refresh | success, failed (expired) |
| `auth.password_change` | Password update | success, failed |

**Resource Actions (Priority: Medium):**

| Action | Description |
|--------|-------------|
| `project.create` | Project created |
| `project.update` | Project updated |
| `project.delete` | Project soft deleted |
| `project.restore` | Project restored from trash |
| `workspace.create` | Workspace created |
| `workspace.update` | Workspace updated |
| `workspace.delete` | Workspace deleted |
| `playground.start` | Container started |
| `playground.stop` | Container stopped |

**Metadata Examples:**

```json
// auth.login (success)
{"method": "email", "email": "user@example.com"}

// auth.login (failed)
{"method": "email", "email": "user@example.com", "reason": "invalid_password"}

// auth.login_oauth (success)
{"provider": "google", "email": "user@gmail.com"}

// project.create
{"project_name": "My Notebook", "workspace_id": "abc-123"}
```

---

## Relationships

| Parent | Child | Relationship | On Delete |
|--------|-------|--------------|-----------|
| users | workspaces | 1:N | CASCADE |
| users | projects | 1:N | CASCADE |
| users | sessions | 1:N | CASCADE |
| users | activity_logs | 1:N | SET NULL |
| workspaces | projects | 1:N (optional) | SET NULL |
| projects | playgrounds | 1:1 | CASCADE |

---

## Storage Architecture

### Database vs MinIO

| Data Type | Storage | Reason |
|-----------|---------|--------|
| User accounts | MySQL | Relational, auth queries |
| Project metadata | MySQL | Relational, ownership |
| Session tokens | MySQL | Transactional, expiration |
| Notebook content | MinIO | Large JSON, versioning |
| Chat history | MinIO | Large JSON, multi-chat |
| Activity logs | MySQL | Time-series, analytics |

### MinIO Folder Structure

```
notebooks/                          # Bucket
└── {MM-YYYY}/                      # Monthly partition
    └── {project_id}/               # Project folder
        ├── notebook.json           # Notebook cells
        └── chats/                  # Chat sessions
            ├── default.json        # Default chat
            ├── {chat_id}.json      # Named chats
            └── index.json          # Chat metadata
```

---

## Common Queries

### Get user's workspaces with project counts
```sql
SELECT
    w.id,
    w.name,
    w.color,
    w.icon,
    w.is_default,
    w.sort_order,
    COUNT(p.id) AS project_count
FROM workspaces w
LEFT JOIN projects p ON w.id = p.workspace_id
    AND p.is_archived = FALSE
    AND p.deleted_at IS NULL
WHERE w.user_id = ?
  AND w.is_deleted = FALSE
GROUP BY w.id
ORDER BY w.sort_order, w.created_at;
```

### Get user's active projects with playground status
```sql
SELECT
    p.id,
    p.name,
    p.description,
    p.workspace_id,
    p.created_at,
    p.updated_at,
    pg.status AS playground_status,
    pg.started_at AS playground_started_at,
    w.name AS workspace_name,
    w.color AS workspace_color
FROM projects p
LEFT JOIN playgrounds pg ON p.id = pg.project_id
LEFT JOIN workspaces w ON p.workspace_id = w.id
WHERE p.user_id = ?
  AND p.is_archived = FALSE
  AND p.deleted_at IS NULL
ORDER BY p.updated_at DESC;
```

### Get projects in a specific workspace
```sql
SELECT
    p.id,
    p.name,
    p.description,
    p.created_at,
    p.updated_at,
    pg.status AS playground_status
FROM projects p
LEFT JOIN playgrounds pg ON p.id = pg.project_id
WHERE p.workspace_id = ?
  AND p.is_archived = FALSE
  AND p.deleted_at IS NULL
ORDER BY p.updated_at DESC;
```

### Get uncategorized projects (no workspace)
```sql
SELECT
    p.id,
    p.name,
    p.description,
    p.created_at,
    p.updated_at
FROM projects p
WHERE p.user_id = ?
  AND p.workspace_id IS NULL
  AND p.is_archived = FALSE
  AND p.deleted_at IS NULL
ORDER BY p.updated_at DESC;
```

### Check user project quota
```sql
SELECT
    u.max_projects,
    COUNT(p.id) AS current_projects,
    (u.max_projects - COUNT(p.id)) AS remaining
FROM users u
LEFT JOIN projects p ON u.id = p.user_id
    AND p.is_archived = FALSE
    AND p.deleted_at IS NULL
WHERE u.id = ?
GROUP BY u.id;
```

### Find stale playgrounds for cleanup
```sql
SELECT
    pg.*,
    p.name AS project_name,
    u.email AS user_email
FROM playgrounds pg
JOIN projects p ON pg.project_id = p.id
JOIN users u ON p.user_id = u.id
WHERE pg.status = 'running'
  AND pg.last_activity_at < DATE_SUB(NOW(), INTERVAL 1 HOUR);
```

### Cleanup expired sessions
```sql
DELETE FROM sessions
WHERE expires_at < NOW()
   OR is_revoked = TRUE;
```

---

## Deprecated Columns

These columns are kept for backward compatibility but are no longer used:

| Table | Column | Reason |
|-------|--------|--------|
| projects | llm_provider | LLM provider is now selected at runtime in chat |
| projects | llm_model | LLM model is now selected at runtime in chat |

---

## Recent Changes

### Workspaces Feature (Added)
- New `workspaces` table for organizing projects into groups
- New `workspace_id` column in `projects` table (optional FK)
- Projects can be moved between workspaces or left uncategorized
- Workspace deletion sets project `workspace_id` to NULL (SET NULL)

---

## Migrations

Database migrations are stored in `scripts/migrations/`. See `scripts/migrations/README.md` for details.

### Running Migrations

For existing databases, run the migration scripts to update the schema:

```bash
# Via Docker (recommended)
docker exec -i ainotebook-mysql mysql -u root -p"$MYSQL_ROOT_PASSWORD" ainotebook < scripts/migrations/002_add_audit_logs_status.sql

# Direct MySQL
mysql -u root -p ainotebook < scripts/migrations/002_add_audit_logs_status.sql
```

> **Note:** Replace `$MYSQL_ROOT_PASSWORD` with your actual password or set it as an environment variable.

### Migration History

| Migration | Description | Date |
|-----------|-------------|------|
| 001 | Initial schema (init-db.sql) | 2024-12 |
| 002 | Add status column to activity_logs | 2024-12-12 |

---

## Recent Changes

### Audit Log Enhancement (2024-12-12)
- Added `status` column to `activity_logs` table (success/failed/denied)
- Added `idx_activity_status` index for filtering by status
- Added `idx_activity_user_action` composite index for user audit queries

### Google OAuth Support (2024-12-12)
- OAuth provider and oauth_id columns already existed in users table
- No schema changes required, just new code paths

### Workspaces Feature (Added Previously)
- New `workspaces` table for organizing projects into groups
- New `workspace_id` column in `projects` table (optional FK)
- Projects can be moved between workspaces or left uncategorized
- Workspace deletion sets project `workspace_id` to NULL (SET NULL)

---

## Future Considerations

Potential schema additions for future features:

| Feature | Tables/Columns Needed |
|---------|----------------------|
| Team collaboration | `teams`, `team_members`, `project_permissions` |
| API keys | `api_keys` (user_id, key_hash, scopes, expires_at) |
| Usage quotas | `usage_stats` (user_id, period, compute_minutes, storage_bytes) |
| Notebook versions | `notebook_versions` (project_id, version, snapshot_path) |
| Scheduled jobs | `scheduled_runs` (project_id, cron, last_run, next_run) |
