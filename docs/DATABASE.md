# Database Schema Documentation

## Overview

The AI Notebook Platform uses **MySQL 8.0** as its primary database.

- **Character Set:** utf8mb4 (full Unicode support, including emojis)
- **Collation:** utf8mb4_unicode_ci
- **Primary Keys:** UUID v4 (CHAR(36))

---

## Entity Relationship Diagram

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│     users       │       │    projects     │       │   playgrounds   │
├─────────────────┤       ├─────────────────┤       ├─────────────────┤
│ id (PK)         │──┐    │ id (PK)         │──┐    │ id (PK)         │
│ email           │  │    │ user_id (FK)    │  │    │ project_id (FK) │
│ name            │  └───<│ name            │  └───<│ container_id    │
│ password_hash   │       │ description     │       │ container_name  │
│ oauth_provider  │       │ storage_path    │       │ internal_url    │
│ oauth_id        │       │ llm_provider    │       │ status          │
│ max_projects    │       │ is_archived     │       │ started_at      │
│ is_active       │       │ created_at      │       │ last_activity   │
│ created_at      │       │ updated_at      │       └─────────────────┘
└─────────────────┘       └─────────────────┘
        │                         │
        │                         │
        │                         ▼
        │                 ┌─────────────────┐
        │                 │  chat_messages  │
        │                 ├─────────────────┤
        │                 │ id (PK)         │
        │                 │ project_id (FK) │
        │                 │ role            │
        │                 │ content         │
        │                 │ metadata (JSON) │
        │                 │ created_at      │
        │                 └─────────────────┘
        │
        ▼
┌─────────────────┐       ┌─────────────────┐
│    sessions     │       │  activity_logs  │
├─────────────────┤       ├─────────────────┤
│ id (PK)         │       │ id (PK, AUTO)   │
│ user_id (FK)    │       │ user_id (FK)    │
│ refresh_token   │       │ action          │
│ expires_at      │       │ resource_type   │
│ is_revoked      │       │ resource_id     │
│ created_at      │       │ metadata (JSON) │
└─────────────────┘       │ created_at      │
                          └─────────────────┘
```

---

## Tables

### 1. `users`

Stores user accounts. Supports local (email/password) and OAuth authentication.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | CHAR(36) | PK | UUID v4 |
| `email` | VARCHAR(255) | UNIQUE, NOT NULL | User's email |
| `name` | VARCHAR(255) | NULL | Display name |
| `avatar_url` | VARCHAR(500) | NULL | Profile picture URL |
| `password_hash` | VARCHAR(255) | NULL | Bcrypt hash (NULL for OAuth) |
| `oauth_provider` | ENUM | DEFAULT 'local' | 'local', 'google', 'github' |
| `oauth_id` | VARCHAR(255) | NULL | OAuth provider user ID |
| `max_projects` | INT | DEFAULT 5 | Max notebooks allowed |
| `is_active` | BOOLEAN | DEFAULT TRUE | Account status |
| `is_verified` | BOOLEAN | DEFAULT FALSE | Email verified |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Creation time |
| `updated_at` | TIMESTAMP | ON UPDATE NOW() | Last update |
| `last_login_at` | TIMESTAMP | NULL | Last login time |

**Indexes:**
- `uk_users_email` - Unique on email
- `uk_users_oauth` - Unique on (oauth_provider, oauth_id)
- `idx_users_active` - On is_active
- `idx_users_created` - On created_at

---

### 2. `projects`

Stores notebook projects. Each project has one `.ipynb` file in MinIO.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | CHAR(36) | PK | UUID v4 |
| `user_id` | CHAR(36) | FK → users.id | Owner |
| `name` | VARCHAR(255) | NOT NULL | Project name |
| `description` | TEXT | NULL | Description |
| `storage_path` | VARCHAR(500) | NOT NULL | MinIO path |
| `llm_provider` | ENUM | DEFAULT 'ollama' | Preferred LLM |
| `llm_model` | VARCHAR(100) | NULL | Specific model |
| `is_archived` | BOOLEAN | DEFAULT FALSE | Soft delete |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Creation time |
| `updated_at` | TIMESTAMP | ON UPDATE NOW() | Last update |
| `last_opened_at` | TIMESTAMP | NULL | Last opened |

**Indexes:**
- `idx_projects_user` - On user_id
- `idx_projects_user_active` - On (user_id, is_archived)
- `idx_projects_updated` - On updated_at

**Storage Path Format:**
```
{user_id}/{project_id}/notebook.ipynb
```

---

### 3. `playgrounds`

Tracks active container instances. Only one playground per project at a time.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | CHAR(36) | PK | UUID v4 |
| `project_id` | CHAR(36) | FK, UNIQUE | One per project |
| `container_id` | VARCHAR(255) | UNIQUE, NOT NULL | Docker ID |
| `container_name` | VARCHAR(255) | NOT NULL | For routing |
| `internal_url` | VARCHAR(500) | NOT NULL | Internal URL |
| `internal_secret` | VARCHAR(255) | NOT NULL | Auth token |
| `status` | ENUM | NOT NULL | Container state |
| `error_message` | TEXT | NULL | Error details |
| `memory_limit_mb` | INT | DEFAULT 2048 | Memory limit |
| `cpu_limit` | DECIMAL(3,2) | DEFAULT 1.00 | CPU limit |
| `started_at` | TIMESTAMP | DEFAULT NOW() | Start time |
| `last_activity_at` | TIMESTAMP | DEFAULT NOW() | Last activity |
| `stopped_at` | TIMESTAMP | NULL | Stop time |

**Status Values:**
- `starting` - Container being created
- `running` - Active and healthy
- `stopping` - Shutdown in progress
- `stopped` - Terminated
- `error` - Failed state

**Container Name Format:**
```
playground-{project_id_short}
```

---

### 4. `chat_messages`

Stores LLM chat history. Replaces JSON file storage.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | CHAR(36) | PK | UUID v4 |
| `project_id` | CHAR(36) | FK → projects.id | Project |
| `role` | ENUM | NOT NULL | 'user', 'assistant', 'system' |
| `content` | TEXT | NOT NULL | Message content |
| `metadata` | JSON | NULL | Model info, tokens, etc. |
| `tool_calls` | JSON | NULL | Tool invocations |
| `tool_results` | JSON | NULL | Tool results |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Message time |

**Metadata JSON Structure:**
```json
{
  "model": "gpt-4o",
  "provider": "openai",
  "tokens": {
    "prompt": 1500,
    "completion": 500,
    "total": 2000
  },
  "llm_steps": [
    {
      "type": "tool_call",
      "name": "execute_python_code",
      "args": {"code": "print('hello')"}
    }
  ]
}
```

---

### 5. `sessions`

Stores JWT refresh tokens. Multiple sessions per user (devices).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | CHAR(36) | PK | UUID v4 |
| `user_id` | CHAR(36) | FK → users.id | Owner |
| `refresh_token_hash` | VARCHAR(255) | NOT NULL | Token hash |
| `user_agent` | VARCHAR(500) | NULL | Browser/device |
| `ip_address` | VARCHAR(45) | NULL | Client IP |
| `expires_at` | TIMESTAMP | NOT NULL | Expiration |
| `is_revoked` | BOOLEAN | DEFAULT FALSE | Manually revoked |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Creation time |
| `last_used_at` | TIMESTAMP | NULL | Last refresh |

---

### 6. `activity_logs`

Audit log for tracking user actions. Optional but recommended.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | BIGINT | PK, AUTO_INCREMENT | Log ID |
| `user_id` | CHAR(36) | FK, NULL | Actor (NULL for system) |
| `action` | VARCHAR(100) | NOT NULL | Action name |
| `resource_type` | VARCHAR(50) | NULL | Resource type |
| `resource_id` | CHAR(36) | NULL | Resource ID |
| `metadata` | JSON | NULL | Additional context |
| `ip_address` | VARCHAR(45) | NULL | Client IP |
| `user_agent` | VARCHAR(500) | NULL | Browser/device |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Event time |

**Common Actions:**
- `user.register` - User created account
- `user.login` - User logged in
- `user.logout` - User logged out
- `project.create` - Project created
- `project.delete` - Project deleted
- `playground.start` - Container started
- `playground.stop` - Container stopped
- `chat.message` - Chat message sent

---

## Relationships

| Parent | Child | Type | On Delete |
|--------|-------|------|-----------|
| users | projects | 1:N | CASCADE |
| users | sessions | 1:N | CASCADE |
| users | activity_logs | 1:N | SET NULL |
| projects | playgrounds | 1:1 | CASCADE |
| projects | chat_messages | 1:N | CASCADE |

---

## Stored Procedures

### `cleanup_expired_sessions()`
Removes expired or revoked sessions.

```sql
CALL cleanup_expired_sessions();
```

### `cleanup_stale_playgrounds()`
Marks playgrounds as stopped if inactive for 4+ hours.

```sql
CALL cleanup_stale_playgrounds();
```

---

## Queries

### Get user's projects with playground status
```sql
SELECT
    p.id,
    p.name,
    p.description,
    p.created_at,
    p.updated_at,
    pg.status as playground_status,
    pg.started_at as playground_started_at
FROM projects p
LEFT JOIN playgrounds pg ON p.id = pg.project_id
WHERE p.user_id = ?
  AND p.is_archived = FALSE
ORDER BY p.updated_at DESC;
```

### Check user project quota
```sql
SELECT
    u.max_projects,
    COUNT(p.id) as current_projects,
    (u.max_projects - COUNT(p.id)) as remaining
FROM users u
LEFT JOIN projects p ON u.id = p.user_id AND p.is_archived = FALSE
WHERE u.id = ?
GROUP BY u.id;
```

### Get active playgrounds (for cleanup)
```sql
SELECT
    pg.*,
    p.name as project_name,
    u.email as user_email
FROM playgrounds pg
JOIN projects p ON pg.project_id = p.id
JOIN users u ON p.user_id = u.id
WHERE pg.status = 'running'
  AND pg.last_activity_at < DATE_SUB(NOW(), INTERVAL 1 HOUR);
```

---

## Migration Notes

When migrating from the current JSON-based storage:

1. **Users** - New table, no existing data
2. **Projects** - Map from `notebooks/*.ipynb` files
3. **Chat History** - Migrate from `notebooks/chat_history/*.json`
4. **Sessions** - New table, no existing data

### Migration Script (pseudo-code)
```python
# For each .ipynb file in notebooks/
for notebook_file in glob("notebooks/*.ipynb"):
    # Create project record
    project_id = create_project(name=notebook_file.stem)

    # Upload to MinIO
    upload_to_minio(notebook_file, f"{user_id}/{project_id}/notebook.ipynb")

    # Migrate chat history if exists
    chat_file = f"notebooks/chat_history/{notebook_file.stem}_chat.json"
    if exists(chat_file):
        migrate_chat_history(chat_file, project_id)
```
