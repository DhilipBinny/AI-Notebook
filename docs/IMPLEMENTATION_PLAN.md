# AI Notebook Platform - Implementation Plan

## Overview

Transform the current single-user Jupyter notebook clone into a scalable multi-tenant platform with:
- User authentication (multiple users)
- Project management (n notebooks per user)
- On-demand playground containers (isolated execution environments)
- LLM-powered code assistance

---

## Architecture Decision

### UI Location: **Next.js (Option A)**

The notebook editor UI will be part of the Next.js frontend, NOT inside playground containers.

```
┌─────────────────────────────────────────────────────────────┐
│                        NEXT.JS                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ Login/Auth  │  │  Dashboard  │  │   Notebook Editor   │  │
│  │    Pages    │  │   (List)    │  │   (React Components)│  │
│  └─────────────┘  └─────────────┘  └──────────┬──────────┘  │
└───────────────────────────────────────────────┼─────────────┘
                                                │
                              WebSocket/HTTP API calls
                                                │
                                                ▼
                              ┌─────────────────────────────┐
                              │    PLAYGROUND CONTAINER     │
                              │       (Headless API)        │
                              │                             │
                              │  • FastAPI backend          │
                              │  • Jupyter Kernel Manager   │
                              │  • LLM Client               │
                              │  • NO frontend assets       │
                              └─────────────────────────────┘
```

**Rationale:**
- Single codebase for all UI
- Consistent user experience
- Smaller container images (~200MB vs ~500MB)
- Centralized UI updates
- Better auth token management

---

## Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Frontend** | Next.js 14 (App Router) | SSR, routing, UI |
| **UI Components** | Tailwind CSS + shadcn/ui | Styling |
| **Auth** | NextAuth.js | OAuth + credentials |
| **Master API** | FastAPI | User/project management, orchestration |
| **Database** | MySQL 8.0 | Persistent data |
| **Cache/Sessions** | Redis | Session store, pub/sub |
| **Object Storage** | MinIO (S3-compatible) | Notebooks, outputs |
| **Reverse Proxy** | Nginx | Load balancing, SSL, routing |
| **Containers** | Docker + Docker Compose | Container orchestration |
| **Playground** | FastAPI + Jupyter Client | Code execution, LLM |

---

## System Architecture

```
                           ┌──────────────────────┐
                           │       NGINX          │
                           │   (Reverse Proxy)    │
                           │   Port 80/443        │
                           └──────────┬───────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              │                       │                       │
              ▼                       ▼                       ▼
    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
    │    NEXT.JS      │    │   MASTER API    │    │   PLAYGROUND    │
    │   (Frontend)    │    │   (FastAPI)     │    │   CONTAINERS    │
    │   Port 3000     │    │   Port 8000     │    │   Port 8888     │
    └─────────────────┘    └────────┬────────┘    └─────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
                    ▼               ▼               ▼
             ┌──────────┐   ┌──────────┐    ┌──────────┐
             │  MySQL   │   │  Redis   │    │  MinIO   │
             │  :3306   │   │  :6379   │    │  :9000   │
             └──────────┘   └──────────┘    └──────────┘
```

---

## Directory Structure (Target)

```
ai_notebook_platform/
│
├── docker-compose.yml              # Infrastructure services
├── docker-compose.dev.yml          # Development overrides
├── .env                            # Environment variables
├── .env.example                    # Template
│
├── docs/
│   ├── IMPLEMENTATION_PLAN.md      # This file
│   ├── API.md                      # API documentation
│   └── DATABASE.md                 # Schema documentation
│
├── nginx/
│   ├── nginx.conf                  # Production config
│   └── nginx.dev.conf              # Development config
│
├── master/                         # Master API (Control Plane)
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py                 # FastAPI app
│       ├── config.py               # Settings
│       ├── auth/                   # Authentication
│       │   ├── jwt.py
│       │   ├── oauth.py
│       │   └── middleware.py
│       ├── users/                  # User management
│       │   ├── models.py
│       │   ├── schemas.py
│       │   ├── routes.py
│       │   └── service.py
│       ├── projects/               # Project/notebook management
│       │   ├── models.py
│       │   ├── schemas.py
│       │   ├── routes.py
│       │   └── service.py
│       ├── playgrounds/            # Container orchestration
│       │   ├── models.py
│       │   ├── schemas.py
│       │   ├── routes.py
│       │   ├── service.py
│       │   └── docker_client.py
│       └── db/
│           ├── base.py
│           └── session.py
│
├── playground/                     # Playground Image (Data Plane)
│   ├── Dockerfile
│   ├── requirements.txt
│   └── backend/                    # Current backend code (modified)
│       ├── server.py
│       ├── kernel_manager.py
│       ├── session_manager.py
│       ├── storage.py              # NEW: S3 client
│       ├── llm_client.py
│       └── ...
│
├── frontend/                       # Next.js Frontend
│   ├── Dockerfile
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.js
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx                # Landing
│   │   ├── (auth)/
│   │   │   ├── login/
│   │   │   └── register/
│   │   ├── (dashboard)/
│   │   │   ├── projects/
│   │   │   └── settings/
│   │   └── notebook/
│   │       └── [id]/
│   │           └── page.tsx
│   ├── components/
│   │   ├── ui/                     # shadcn components
│   │   ├── auth/
│   │   ├── dashboard/
│   │   └── notebook/               # Converted from current frontend
│   │       ├── NotebookEditor.tsx
│   │       ├── Cell.tsx
│   │       ├── CellOutput.tsx
│   │       ├── ChatPanel.tsx
│   │       └── Toolbar.tsx
│   ├── hooks/
│   ├── lib/
│   └── types/
│
└── scripts/
    ├── init-db.sql                 # Database initialization
    └── setup.sh                    # Setup script
```

---

## Implementation Phases

### Phase 1: Infrastructure Setup ✅ COMPLETED
- [x] Document implementation plan
- [x] Docker Compose for MySQL + MinIO + Redis
- [x] Database schema design
- [x] Initial table creation

### Phase 2: Master API (Control Plane) ✅ COMPLETED
- [x] FastAPI project setup
- [x] Database models (SQLAlchemy)
- [x] User authentication (JWT)
- [x] User CRUD endpoints
- [x] Project CRUD endpoints
- [x] Playground orchestration service
- [x] Health check endpoints
- [x] Notebook S3 storage endpoints
- [x] Chat history storage endpoints
- [x] Internal API for playground-to-master communication

### Phase 3: Playground Containerization ✅ COMPLETED
- [x] Modify current backend for headless operation
- [x] Add S3 storage client (via Master API lazy load)
- [x] Add internal auth validation (X-Internal-Secret)
- [x] Create Dockerfile
- [x] Test container lifecycle
- [x] Multi-provider LLM support (Ollama, OpenAI, Anthropic, Gemini)
- [x] Tool execution modes (manual, auto, ai_decide)

### Phase 4: Next.js Frontend ✅ COMPLETED
- [x] Project setup with Tailwind + shadcn
- [x] Auth pages (login, register)
- [x] Dashboard (project list)
- [x] Convert notebook UI to React components
- [x] WebSocket integration for kernel
- [x] Chat panel integration
- [x] Auto-save before chat
- [x] Zustand state management

### Phase 5: Nginx + Integration ✅ COMPLETED
- [x] Nginx configuration
- [x] Dynamic playground routing
- [x] End-to-end testing
- [ ] SSL/TLS setup (planned for production)

### Phase 6: Production Hardening 🔄 IN PROGRESS
- [x] Resource limits on containers
- [x] Idle timeout auto-shutdown
- [x] Health checks
- [ ] Logging aggregation
- [ ] Backup strategy
- [ ] Rate limiting
- [ ] OAuth integration (Google, GitHub)

---

## API Endpoints (Master API)

### Authentication
```
POST   /api/auth/register          # Create account
POST   /api/auth/login             # Login (credentials)
POST   /api/auth/login/google      # OAuth login
POST   /api/auth/login/github      # OAuth login
POST   /api/auth/refresh           # Refresh token
POST   /api/auth/logout            # Logout
GET    /api/auth/me                # Current user
```

### Users
```
GET    /api/users/me               # Get current user
PATCH  /api/users/me               # Update profile
DELETE /api/users/me               # Delete account
```

### Projects
```
GET    /api/projects               # List user's projects
POST   /api/projects               # Create project
GET    /api/projects/:id           # Get project details
PATCH  /api/projects/:id           # Update project
DELETE /api/projects/:id           # Delete project
GET    /api/projects/:id/notebook  # Download notebook file
PUT    /api/projects/:id/notebook  # Upload notebook file
```

### Playgrounds
```
GET    /api/projects/:id/playground        # Get playground status
POST   /api/projects/:id/playground/start  # Start playground
POST   /api/projects/:id/playground/stop   # Stop playground
GET    /api/projects/:id/playground/logs   # Get container logs
```

### Chat History
```
GET    /api/projects/:id/chat              # Get chat history
DELETE /api/projects/:id/chat              # Clear chat history
```

---

## Database Schema

See `scripts/init-db.sql` for full schema.

### Tables Overview

| Table | Purpose |
|-------|---------|
| `users` | User accounts |
| `projects` | Notebook projects |
| `playgrounds` | Active container instances |
| `chat_messages` | Chat history per project |
| `sessions` | Refresh tokens |

### Key Relationships
```
users (1) ──── (n) projects
projects (1) ──── (0..1) playgrounds (active container)
projects (1) ──── (n) chat_messages
users (1) ──── (n) sessions
```

---

## Environment Variables

```bash
# Database
MYSQL_ROOT_PASSWORD=your_secure_password
MYSQL_DATABASE=ainotebook
DATABASE_URL=mysql+aiomysql://root:${MYSQL_ROOT_PASSWORD}@mysql:3306/ainotebook

# Redis
REDIS_URL=redis://redis:6379

# MinIO (S3)
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
S3_ENDPOINT=http://minio:9000
S3_ACCESS_KEY=${MINIO_ROOT_USER}
S3_SECRET_KEY=${MINIO_ROOT_PASSWORD}
S3_BUCKET=notebooks

# Auth
JWT_SECRET=your_jwt_secret_key_min_32_chars
JWT_ALGORITHM=HS256
JWT_EXPIRY_MINUTES=30
REFRESH_TOKEN_EXPIRY_DAYS=7

# NextAuth
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=your_nextauth_secret

# OAuth (optional)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=

# Playground
PLAYGROUND_IMAGE=ainotebook/playground:latest
PLAYGROUND_MEMORY_LIMIT=2g
PLAYGROUND_CPU_LIMIT=1
PLAYGROUND_IDLE_TIMEOUT=3600

# LLM (for playgrounds)
OLLAMA_HOST=http://host.docker.internal:11434
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GOOGLE_API_KEY=
```

---

## Next Steps

1. **Run infrastructure**: `docker-compose up -d mysql minio redis`
2. **Initialize database**: Run `scripts/init-db.sql`
3. **Start Master API development**
4. **Containerize playground**
5. **Build Next.js frontend**

---

## Notes

- All times stored in UTC
- UUIDs used for all primary keys
- Soft deletes for projects (is_archived flag)
- Chat history stored in DB, not JSON files
- Notebooks stored in MinIO, not local filesystem
