# AI Notebook Platform - Business Logic

> Living document. Last updated: 2026-02-21

## 1. User Lifecycle

### Registration & Access Control
- **Invite-only**: Public signup is disabled. Users must provide a valid invite code during registration.
- **Invite flow**: Admin creates invite (optionally locked to email) → user receives code → registers with code → code is redeemed.
- **OAuth**: Google OAuth login supported. New OAuth accounts still require invite code on first login. Existing accounts can login freely.
- **Initial state**: On registration → credit balance initialized ($10.00) → user can create projects.

### Roles
| Role | Capabilities |
|------|-------------|
| **User** | Create/manage projects, use notebooks, use LLM chat, manage own API keys |
| **Admin** | All user capabilities + manage invitations, adjust credits, manage LLM pricing, create/manage templates |

### Account Limits
- `max_projects`: Default 5 per user (configurable per user via DB)
- Projects use soft delete (`deleted_at` timestamp), don't count toward limit
- `is_active`: Admin can deactivate accounts

---

## 2. Project Model

### Structure
- Each project = one Jupyter notebook (`.ipynb`) stored in S3/MinIO
- S3 path: `{mm-yyyy}/{project_id}/notebook.ipynb`
- Chat history: `{mm-yyyy}/{project_id}/chats/{chat_session_id}.json`
- File uploads: `{mm-yyyy}/{project_id}/uploads/{filename}`

### Constraints
- Project names: max 255 chars
- One notebook per project
- Projects belong to optional workspaces (folders)
- Soft delete: `deleted_at` set, project excluded from queries but data retained
- Archive: `is_archived` flag hides from active view

---

## 3. Container Model (Playgrounds)

### One Container Per User
- Each user gets at most **one** Docker container at a time (not per project).
- Container name pattern: `playground-{user_id[:8]}`
- Container tracks the "active project" — user can switch projects without stopping the container.

### Project Switching
- On switch: save current workspace → restart kernel (clean state) → load new project files from S3
- Kernel restart ensures no variable leakage between projects.

### Resource Limits
| Resource | Default | Config |
|----------|---------|--------|
| Memory | 4 GB | `PLAYGROUND_MEMORY_LIMIT` |
| CPU | 4 cores | `PLAYGROUND_CPU_LIMIT` |
| Idle timeout | 1 hour | `PLAYGROUND_IDLE_TIMEOUT` |

### Lifecycle
1. User opens a project → container starts (or reuses existing)
2. Container reports activity via heartbeat
3. After idle timeout → container auto-stopped
4. Background task checks every 5 minutes for stale containers

### Container Status
`starting` → `running` → `stopping` → `stopped`; can transition to `error` from any state.

---

## 4. LLM Access Rules

### Supported Providers
| Provider | API Key Config | Models |
|----------|---------------|--------|
| Gemini | `GEMINI_API_KEY` or user key | gemini-2.0-flash, gemini-2.5-pro, etc. |
| OpenAI | `OPENAI_API_KEY` or user key | gpt-4o, gpt-4o-mini, etc. |
| Anthropic | `ANTHROPIC_API_KEY` or user key | claude-sonnet-4-20250514, etc. |
| Ollama | `OLLAMA_URL` (no key needed) | Local models — always free |

### Key Priority (per request)
1. **User's own API key** (if configured for the provider) → bypasses credits
2. **Platform API key** (global env var) → deducts from user's credit balance
3. **Ollama** → always free (local inference)

### Key Injection
- User keys are injected per-request via HTTP headers (`X-User-OpenAI-Key`, etc.)
- No container restart needed when keys change
- Keys stored Fernet-encrypted in DB; never returned in plaintext to frontend

---

## 5. Credit System

### Balance
- Initial balance: $10.00 (1000 cents) on registration
- Stored as integer cents to avoid floating-point issues
- Hard stop at $0 — requests rejected when insufficient credits

### Cost Calculation
```
cost = (input_tokens / 1M * input_price + output_tokens / 1M * output_price) * margin_multiplier
```
- `margin_multiplier`: Default 1.30 (30% margin)
- Pricing stored in `llm_pricing` table per provider/model
- Admin can update pricing at any time

### Usage Tracking Flow
1. **Pre-flight** (master API): Estimate cost, check balance, reject if insufficient
2. **Execution** (playground): LLM call happens, actual tokens accumulated
3. **Post-flight** (master API): Parse actual usage from SSE `done` event, calculate real cost, deduct from balance, record in `usage_records`

### Own Key Bypass
- If user uses their own API key: usage is **recorded** (for analytics) but **not deducted** from credits
- `usage_records.is_own_key = TRUE`, `cost_cents = 0`

---

## 6. Template System

### Purpose
Pre-built notebooks for educational use (crash course, workshops).

### Structure
- Templates stored in S3: `templates/{template_id}/notebook.ipynb`
- Metadata: name, description, category, difficulty level, estimated time, tags
- Admin creates templates (or converts existing projects to templates)
- `is_public` flag controls visibility to users

### Fork Flow
1. User browses template gallery (filtered by category/difficulty)
2. Clicks "Use Template" → creates new project with template notebook copied
3. User owns the forked project — can modify freely
4. Original template unchanged

### Categories (for AGAI-101 course)
- LLM Basics
- Prompt Engineering
- RAG & Embeddings
- Fine-Tuning
- AI Agents
- (Extensible via `category` field)

---

## 7. Admin Capabilities

| Area | Actions |
|------|---------|
| **Invitations** | Create (single/batch), list, deactivate, view usage |
| **Credits** | View any user's balance, adjust balance (add/deduct), set reason |
| **Pricing** | View/update per-model pricing, adjust margin multiplier |
| **Templates** | Create, edit, delete, publish/unpublish, create from existing project |

Admin routes are protected by `get_current_admin_user` dependency (checks `user.is_admin`).

---

## 8. Security Constraints

- JWT authentication: Access tokens (30 min), Refresh tokens (7 days, HMAC-SHA256 hashed)
- WebSocket connections require `?token=` query parameter with valid JWT
- Playground containers use HMAC internal secret for master ↔ playground communication
- API keys encrypted with Fernet (AES-128-CBC) before storage
- Package installation validated with regex to prevent injection
- OAuth redirect URLs use configured base URL (not request Host header)
- CORS configured per environment

---

## 9. Storage Architecture

| Data | Storage | Path Pattern |
|------|---------|-------------|
| Notebooks | S3/MinIO | `{mm-yyyy}/{project_id}/notebook.ipynb` |
| Chat history | S3/MinIO | `{mm-yyyy}/{project_id}/chats/{session_id}.json` |
| File uploads | S3/MinIO | `{mm-yyyy}/{project_id}/uploads/{filename}` |
| Templates | S3/MinIO | `templates/{template_id}/notebook.ipynb` |
| User data | MySQL | `users`, `projects`, `playgrounds`, etc. |
| Sessions | MySQL | `sessions` table (refresh tokens) |

---

## 10. Configuration (Environment Variables)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | dev default | MySQL connection string |
| `JWT_SECRET` | Prod | dev key | Must be 32+ chars in production |
| `REQUIRE_INVITE_CODE` | No | `false` | Enable invite-only registration |
| `ENCRYPTION_KEY` | Prod | — | Fernet key for API key encryption |
| `PLAYGROUND_IMAGE` | No | `ainotebook-playground:latest` | Docker image for containers |
| `PLAYGROUND_IDLE_TIMEOUT` | No | `3600` | Seconds before idle shutdown |
| `PLAYGROUND_MEMORY_LIMIT` | No | `4g` | Container memory limit |
| `PLAYGROUND_CPU_LIMIT` | No | `4.0` | Container CPU limit |
| `GEMINI_API_KEY` | No | — | Platform Gemini key |
| `OPENAI_API_KEY` | No | — | Platform OpenAI key |
| `ANTHROPIC_API_KEY` | No | — | Platform Anthropic key |
| `OLLAMA_URL` | No | — | Ollama server URL |
