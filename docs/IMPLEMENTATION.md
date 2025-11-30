# AI Notebook Platform - Implementation Documentation

## Overview

This document describes the complete transformation of a single-user Jupyter notebook clone with LLM capabilities into a **scalable multi-tenant platform**.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              NGINX (Port 80)                                │
│  Routes:                                                                    │
│    /              → Next.js Frontend (Port 3000)                           │
│    /api/*         → Master API (Port 8001)                                 │
│    /playground/*  → Dynamic Playground Containers (Port 8888 each)         │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
        ┌─────────────────────────────┼─────────────────────────────┐
        │                             │                             │
        ▼                             ▼                             ▼
┌───────────────┐          ┌───────────────────┐         ┌─────────────────┐
│   Frontend    │          │    Master API     │         │   Playground    │
│   (Next.js)   │          │    (FastAPI)      │         │   Containers    │
│               │          │                   │         │                 │
│ • Login/Auth  │  ◄────►  │ • User Auth (JWT) │ ◄────►  │ • Jupyter Kernel│
│ • Dashboard   │          │ • Projects CRUD   │         │ • LLM Chat      │
│ • Notebook UI │          │ • Container Orch  │         │ • Code Exec     │
│ • Chat Panel  │          │ • Session Mgmt    │         │ • WebSocket     │
└───────────────┘          └───────────────────┘         └─────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    │                 │                 │
                    ▼                 ▼                 ▼
             ┌───────────┐    ┌───────────┐    ┌───────────────┐
             │   MySQL   │    │   Redis   │    │     MinIO     │
             │  (3307)   │    │  (6380)   │    │  (9002/9003)  │
             │           │    │           │    │               │
             │ • Users   │    │ • Sessions│    │ • Notebooks   │
             │ • Projects│    │ • Cache   │    │ • Files       │
             │ • State   │    │           │    │               │
             └───────────┘    └───────────┘    └───────────────┘
```

## Directory Structure

```
ai_notebook_clone/
├── backend/                    # Original backend (reference)
├── frontend/                   # Original frontend (reference)
├── docs/
│   ├── DATABASE.md            # Database schema docs
│   └── IMPLEMENTATION.md      # This file
├── infrastructure/
│   ├── docker-compose.yml     # MySQL, Redis, MinIO
│   └── .env                   # Infrastructure config
├── master/                    # Master API (Control Plane)
│   ├── app/
│   │   ├── auth/             # Authentication (JWT, sessions)
│   │   ├── users/            # User management
│   │   ├── projects/         # Project CRUD
│   │   ├── playgrounds/      # Container orchestration
│   │   ├── chat/             # Chat message storage
│   │   ├── core/             # Config, security utils
│   │   └── db/               # Database session, base
│   ├── requirements.txt
│   └── .env
├── nginx/
│   └── nginx.conf            # Reverse proxy config
├── playground/               # Playground Container Image
│   ├── backend/              # Adapted from original backend
│   ├── Dockerfile
│   └── requirements.txt
├── scripts/
│   └── init-db.sql          # Database schema
├── web/                      # Next.js Frontend
│   ├── src/
│   │   ├── app/
│   │   │   ├── auth/        # Login, Register pages
│   │   │   ├── dashboard/   # Project listing
│   │   │   └── notebook/    # Notebook editor
│   │   ├── components/
│   │   ├── lib/             # API client, stores
│   │   └── types/           # TypeScript types
│   ├── package.json
│   └── next.config.ts
└── docker-compose.yml        # Full stack compose
```

## Components

### 1. Infrastructure Services

**MySQL 8.0** (Port 3307)
- Database: `ainotebook`
- Password: `ainotebook_dev_2024`
- Tables: users, projects, playgrounds, sessions, chat_messages

**Redis 7** (Port 6380)
- Session storage
- Cache layer (future)

**MinIO** (Ports 9002 API, 9003 Console)
- S3-compatible object storage
- Bucket: `notebooks`
- Credentials: `minioadmin` / `minioadmin123`

### 2. Master API (FastAPI)

**Location:** `/master`

**Endpoints:**
```
POST   /api/auth/register     # Create account
POST   /api/auth/login        # Login, get JWT
POST   /api/auth/logout       # Invalidate session
POST   /api/auth/refresh      # Refresh access token

GET    /api/users/me          # Current user info
PATCH  /api/users/me          # Update profile

GET    /api/projects          # List user's projects
POST   /api/projects          # Create project
GET    /api/projects/{id}     # Get project details
PATCH  /api/projects/{id}     # Update project
DELETE /api/projects/{id}     # Delete project

GET    /api/projects/{id}/playground        # Playground status
POST   /api/projects/{id}/playground/start  # Start container
POST   /api/projects/{id}/playground/stop   # Stop container
GET    /api/projects/{id}/playground/logs   # Container logs
POST   /api/projects/{id}/playground/activity  # Heartbeat
```

**Key Files:**
- `app/core/config.py` - Settings from environment
- `app/auth/service.py` - JWT token management
- `app/playgrounds/docker_client.py` - Docker SDK wrapper
- `app/playgrounds/service.py` - Container lifecycle

### 3. Playground Container

**Location:** `/playground`
**Image:** `ainotebook-playground:latest`

**Features:**
- Headless Jupyter kernel (no frontend)
- Multi-provider LLM support:
  - Ollama (default, local)
  - OpenAI
  - Anthropic Claude
  - Google Gemini
- WebSocket streaming for code execution
- Internal secret authentication (container-to-master)

**Endpoints:**
```
GET    /health               # Health check (no auth)
GET    /status               # Detailed status
POST   /chat                 # LLM chat
POST   /chat/execute-tools   # Execute approved tool calls
POST   /llm/provider         # Switch LLM provider
GET    /llm/tool-mode        # Get tool execution mode
POST   /llm/tool-mode        # Set tool execution mode
WS     /ws/execute           # Code execution streaming
```

**Environment Variables:**
```
PLAYGROUND_PORT=8888
LLM_PROVIDER=ollama
OLLAMA_URL=http://host.docker.internal:11434/v1
OLLAMA_MODEL=qwen3-coder:30b
TOOL_EXECUTION_MODE=manual
INTERNAL_SECRET=<generated-per-container>
```

### 4. Next.js Frontend

**Location:** `/web`
**Port:** 3000

**Pages:**
- `/auth/login` - Login form
- `/auth/register` - Registration form
- `/dashboard` - Project list, create new
- `/notebook/[id]` - Notebook editor with:
  - Cell management (code/markdown)
  - Playground start/stop
  - Chat sidebar (AI assistant)

**State Management:** Zustand stores
- `useAuthStore` - User authentication state
- `useProjectsStore` - Projects list and current project
- `useNotebookStore` - Cells, selection, dirty state

**API Client:** `/lib/api.ts`
- Axios instance with JWT interceptor
- Auto-redirect on 401

### 5. Nginx Reverse Proxy

**Location:** `/nginx/nginx.conf`
**Port:** 80

**Routing:**
```
/                    → frontend:3000
/_next/webpack-hmr   → frontend:3000 (HMR WebSocket)
/api/*               → master_api:8001
/health              → master_api:8001
/playground/{name}/* → {name}:8888 (dynamic container routing)
```

## Database Schema

### Users Table
```sql
CREATE TABLE users (
    id VARCHAR(36) PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    password_hash VARCHAR(255),
    oauth_provider ENUM('local', 'google', 'github') DEFAULT 'local',
    oauth_id VARCHAR(255),
    max_projects INT DEFAULT 5,
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP
);
```

### Projects Table
```sql
CREATE TABLE projects (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    storage_path VARCHAR(500) NOT NULL,
    llm_provider ENUM('ollama', 'openai', 'anthropic', 'gemini') DEFAULT 'ollama',
    llm_model VARCHAR(100),
    is_archived BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_opened_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

### Playgrounds Table
```sql
CREATE TABLE playgrounds (
    id VARCHAR(36) PRIMARY KEY,
    project_id VARCHAR(36) UNIQUE NOT NULL,
    container_id VARCHAR(255) UNIQUE NOT NULL,
    container_name VARCHAR(255) NOT NULL,
    internal_url VARCHAR(500) NOT NULL,
    internal_secret VARCHAR(255) NOT NULL,
    status ENUM('starting', 'running', 'stopping', 'stopped', 'error') DEFAULT 'starting',
    error_message TEXT,
    memory_limit_mb INT DEFAULT 2048,
    cpu_limit FLOAT DEFAULT 1.0,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    stopped_at TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);
```

## Configuration

### Master API Environment (master/.env)
```bash
APP_ENV=development
APP_DEBUG=true
DATABASE_URL=mysql+aiomysql://root:ainotebook_dev_2024@localhost:3307/ainotebook
REDIS_URL=redis://localhost:6380/0
S3_ENDPOINT=http://localhost:9002
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin123
S3_BUCKET_NOTEBOOKS=notebooks
JWT_SECRET=dev_secret_key_change_in_production_32chars_min
PLAYGROUND_IMAGE=ainotebook-playground:latest
PLAYGROUND_NETWORK=ainotebook-network
PLAYGROUND_MEMORY_LIMIT=2g
PLAYGROUND_CPU_LIMIT=1.0
PLAYGROUND_IDLE_TIMEOUT=3600
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
```

### Infrastructure Environment (infrastructure/.env)
```bash
MYSQL_ROOT_PASSWORD=ainotebook_dev_2024
MYSQL_DATABASE=ainotebook
REDIS_PASSWORD=
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin123
```

## Development Setup

### Prerequisites
- Docker & Docker Compose
- Conda (Anaconda/Miniconda)
- Node.js 18+

### Step 1: Start Infrastructure
```bash
cd /home/binny/Desktop/ai_notebook_clone/infrastructure
docker-compose up -d

# Verify
docker-compose ps
```

### Step 2: Build Playground Image
```bash
cd /home/binny/Desktop/ai_notebook_clone/playground
docker build -t ainotebook-playground:latest .
```

### Step 3: Start Master API
```bash
cd /home/binny/Desktop/ai_notebook_clone/master
conda activate ainotebook
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

### Step 4: Start Frontend
```bash
cd /home/binny/Desktop/ai_notebook_clone/web
npm install
npm run dev
```

### Step 5: Access Application
- Frontend: http://localhost:3000
- Master API Docs: http://localhost:8001/docs
- MinIO Console: http://localhost:9003

## Testing the Flow

### 1. Register User
```bash
curl -X POST http://localhost:8001/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password123"}'
```

### 2. Login
```bash
curl -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password123"}'
# Save the access_token from response
```

### 3. Create Project
```bash
curl -X POST http://localhost:8001/api/projects \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "My Notebook", "description": "Test project"}'
# Save the project id
```

### 4. Start Playground
```bash
curl -X POST http://localhost:8001/api/projects/<project_id>/playground/start \
  -H "Authorization: Bearer <access_token>"
```

### 5. Check Playground Status
```bash
curl http://localhost:8001/api/projects/<project_id>/playground \
  -H "Authorization: Bearer <access_token>"
```

## Key Implementation Details

### SQLAlchemy Enum Handling
MySQL stores enum values in lowercase, but Python Enum uses uppercase. Fixed using:
```python
oauth_provider = Column(
    SQLEnum(OAuthProvider, values_callable=lambda obj: [e.value for e in obj]),
    default=OAuthProvider.LOCAL,
    nullable=False
)
```

### DateTime Lazy Loading
Server-generated timestamps weren't available after `flush()`. Fixed by using Python defaults:
```python
created_at = Column(DateTime, default=datetime.utcnow, server_default=func.now())
```

### Docker Container Naming
Containers are named `playground-{project_id[:8]}` for easy routing:
```python
container_name = f"playground-{project.id[:8]}"
```

### Internal Authentication
Playground containers authenticate requests from Master using a per-container secret:
```python
async def verify_internal_secret(x_internal_secret: str = Header(None)):
    if x_internal_secret != INTERNAL_SECRET:
        raise HTTPException(status_code=403)
```

## Recent Updates

### Lazy Load Architecture (Nov 2024)

The notebook data flow has been redesigned to use lazy loading:

**Before:** Frontend synced all cells to Playground before chat
**After:** LLM tools fetch cells on-demand from Master API

Key changes:
- `tool_notebook_cells.py` - Rewritten to call Master API via httpx
- `master/app/internal/routes.py` - New internal endpoints for playground
- `web/src/app/notebook/[id]/page.tsx` - Auto-save before chat
- Removed `/notebook/sync` endpoints from both Master and Playground

See `NOTEBOOK_LAZY_LOAD_ARCHITECTURE.md` for detailed diagrams.

### LLM Tool Functions

Available tools for AI assistant:
- `get_notebook_overview()` - Cell structure and previews
- `get_cell_content(index)` - Full cell content
- `update_cell_content(index, content)` - Modify cells
- `insert_cell(position, content, type)` - Add new cells
- `execute_cell(index)` - Run code and get output
- `execute_python_code(code)` - Arbitrary code execution

### Tool Execution Modes

Three modes for handling LLM tool calls:
- `manual` - User approval required
- `auto` - Automatic execution
- `ai_decide` - LLM determines based on risk

## Future Enhancements

1. **OAuth Integration** - Google, GitHub login
2. **Real-time Collaboration** - WebSocket sync for multi-user editing
3. **Usage Metrics** - Track execution time, LLM tokens
4. **Admin Dashboard** - User management, system stats
5. **Container Auto-scaling** - Based on demand
6. **SSL/TLS** - HTTPS with Let's Encrypt
7. **Rate Limiting** - API throttling via nginx
