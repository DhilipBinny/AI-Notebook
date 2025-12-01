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
          │ 1:N
          ▼
┌─────────────────────┐       ┌─────────────────────┐
│      projects       │       │     playgrounds     │
├─────────────────────┤       ├─────────────────────┤
│ id (PK)             │──────<│ id (PK)             │
│ user_id (FK)        │  1:1  │ project_id (FK,UQ)  │
│ name                │       │ container_id (UQ)   │
│ description         │       │ container_name      │
│ storage_path        │       │ internal_url        │
│ storage_month       │       │ internal_secret     │
│ llm_provider *      │       │ status              │
│ llm_model *         │       │ error_message       │
│ is_archived         │       │ memory_limit_mb     │
│ deleted_at          │       │ cpu_limit           │
│ created_at          │       │ started_at          │
│ updated_at          │       │ last_activity_at    │
│ last_opened_at      │       │ stopped_at          │
└─────────────────────┘       └─────────────────────┘

┌─────────────────────┐       ┌─────────────────────┐
│      sessions       │       │    activity_logs    │
├─────────────────────┤       ├─────────────────────┤
│ id (PK)             │       │ id (PK, AUTO_INCR)  │
│ user_id (FK)        │       │ user_id (FK)        │
│ refresh_token_hash  │       │ action              │
│ user_agent          │       │ resource_type       │
│ ip_address          │       │ resource_id         │
│ expires_at          │       │ metadata (JSON)     │
│ is_revoked          │       │ ip_address          │
│ created_at          │       │ user_agent          │
│ last_used_at        │       │ created_at          │
└─────────────────────┘       └─────────────────────┘

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

### 2. `projects`

Stores notebook projects. Each project maps to files in MinIO storage.

| Column | Type | Null | Key | Default | Description |
|--------|------|------|-----|---------|-------------|
| `id` | CHAR(36) | NO | PK | - | UUID v4 |
| `user_id` | CHAR(36) | NO | FK,IDX | - | Owner reference |
| `name` | VARCHAR(255) | NO | - | - | Project name |
| `description` | TEXT | YES | - | NULL | Description |
| `storage_path` | VARCHAR(500) | NO | - | - | Full MinIO path |
| `storage_month` | VARCHAR(7) | NO | - | - | Folder partition (MM-YYYY) |
| `llm_provider` | ENUM | YES | - | 'ollama' | **Deprecated** |
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

### 3. `playgrounds`

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

### 4. `sessions`

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

### 5. `activity_logs`

Audit log for tracking user actions. Optional for debugging and analytics.

| Column | Type | Null | Key | Default | Description |
|--------|------|------|-----|---------|-------------|
| `id` | BIGINT UNSIGNED | NO | PK | AUTO | Log ID |
| `user_id` | CHAR(36) | YES | FK,IDX | NULL | Actor (NULL for system) |
| `action` | VARCHAR(100) | NO | IDX | - | Action name |
| `resource_type` | VARCHAR(50) | YES | IDX | NULL | Resource type |
| `resource_id` | CHAR(36) | YES | - | NULL | Resource ID |
| `metadata` | JSON | YES | - | NULL | Additional context |
| `ip_address` | VARCHAR(45) | YES | - | NULL | Client IP |
| `user_agent` | VARCHAR(500) | YES | - | NULL | Browser/device |
| `created_at` | TIMESTAMP | NO | IDX | NOW() | Event time |

**Common Actions:**

| Action | Description |
|--------|-------------|
| `user.register` | User created account |
| `user.login` | User logged in |
| `user.logout` | User logged out |
| `project.create` | Project created |
| `project.delete` | Project deleted |
| `playground.start` | Container started |
| `playground.stop` | Container stopped |

---

## Relationships

| Parent | Child | Relationship | On Delete |
|--------|-------|--------------|-----------|
| users | projects | 1:N | CASCADE |
| users | sessions | 1:N | CASCADE |
| users | activity_logs | 1:N | SET NULL |
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

### Get user's active projects with playground status
```sql
SELECT
    p.id,
    p.name,
    p.description,
    p.created_at,
    p.updated_at,
    pg.status AS playground_status,
    pg.started_at AS playground_started_at
FROM projects p
LEFT JOIN playgrounds pg ON p.id = pg.project_id
WHERE p.user_id = ?
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

## Future Considerations

Potential schema additions for future features:

| Feature | Tables/Columns Needed |
|---------|----------------------|
| Team collaboration | `teams`, `team_members`, `project_permissions` |
| API keys | `api_keys` (user_id, key_hash, scopes, expires_at) |
| Usage quotas | `usage_stats` (user_id, period, compute_minutes, storage_bytes) |
| Notebook versions | `notebook_versions` (project_id, version, snapshot_path) |
| Scheduled jobs | `scheduled_runs` (project_id, cron, last_run, next_run) |
