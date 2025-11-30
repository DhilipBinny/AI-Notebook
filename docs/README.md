# AI Notebook Platform

A multi-tenant, AI-powered Jupyter notebook platform with isolated execution environments and intelligent code assistance.

## Project Status

### Completed Features

| Feature | Status | Description |
|---------|--------|-------------|
| Multi-tenant Auth | Done | JWT-based authentication with user registration/login |
| Project Management | Done | Create, list, update, delete notebook projects |
| Dynamic Playgrounds | Done | On-demand Docker containers per project |
| Notebook Editor | Done | Full-featured cell editor (code/markdown) |
| Multi-LLM Support | Done | Ollama, OpenAI, Anthropic Claude, Google Gemini |
| Chat Assistant | Done | AI chat with tool-calling capabilities |
| Lazy Load Architecture | Done | LLM tools fetch notebook data on-demand from S3 |
| Auto-save Before Chat | Done | Ensures LLM sees latest edits |
| Notebook Persistence | Done | S3/MinIO storage with versioning |
| WebSocket Execution | Done | Real-time code execution streaming |

### In Progress / Planned

| Feature | Status | Description |
|---------|--------|-------------|
| OAuth Login | Planned | Google, GitHub authentication |
| Real-time Collaboration | Planned | WebSocket sync for multi-user editing |
| Usage Metrics | Planned | Track execution time, LLM tokens |
| Admin Dashboard | Planned | User management, system stats |
| SSL/TLS | Planned | HTTPS with Let's Encrypt |

---

## Architecture

```
                            ┌──────────────────────────────────┐
                            │          NGINX (Port 80)         │
                            │         Reverse Proxy            │
                            └────────────────┬─────────────────┘
                                             │
              ┌──────────────────────────────┼──────────────────────────────┐
              │                              │                              │
              ▼                              ▼                              ▼
   ┌────────────────────┐       ┌────────────────────┐       ┌────────────────────┐
   │   NEXT.JS (3000)   │       │  MASTER API (8001) │       │     PLAYGROUND     │
   │     Frontend       │       │     FastAPI        │       │    CONTAINERS      │
   │                    │       │                    │       │                    │
   │ • Auth Pages       │◄─────►│ • User Auth (JWT)  │◄─────►│ • Jupyter Kernel   │
   │ • Dashboard        │       │ • Project CRUD     │       │ • LLM Chat Engine  │
   │ • Notebook Editor  │       │ • Container Orch   │       │ • Code Execution   │
   │ • Chat Panel       │       │ • Notebook Storage │       │ • Tool Functions   │
   └────────────────────┘       └─────────┬──────────┘       └────────────────────┘
                                          │
                     ┌────────────────────┼────────────────────┐
                     │                    │                    │
                     ▼                    ▼                    ▼
              ┌───────────┐        ┌───────────┐        ┌───────────┐
              │   MySQL   │        │   Redis   │        │   MinIO   │
              │  (3307)   │        │  (6380)   │        │  (9002)   │
              │           │        │           │        │           │
              │ • Users   │        │ • Sessions│        │ • Notebooks│
              │ • Projects│        │ • Cache   │        │ • Outputs │
              │ • State   │        │           │        │ • Avatars │
              └───────────┘        └───────────┘        └───────────┘
```

---

## Unique Features

### 1. Lazy Load Architecture for LLM Tools

Unlike traditional notebook sync approaches, our platform uses a **lazy load** pattern:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SINGLE SOURCE OF TRUTH                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   Frontend ────► Master API ────► S3/MinIO (notebooks stored here)  │
│                       ▲                                              │
│                       │ On-demand API calls                          │
│                       │                                              │
│                  Playground                                          │
│                  (LLM tools fetch only what they need)              │
│                                                                      │
│   Benefits:                                                          │
│   • Zero pre-sync overhead                                          │
│   • No sync conflicts (single source of truth)                      │
│   • Stateless playground containers                                 │
│   • Efficient: LLM only fetches cells it needs                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 2. LLM Tool Functions

The AI assistant has access to powerful notebook manipulation tools:

| Tool | Description |
|------|-------------|
| `get_notebook_overview()` | Get structure and preview of all cells |
| `get_cell_content(index)` | Read full content of specific cell |
| `update_cell_content(index, content)` | Modify cell content |
| `insert_cell(position, content, type)` | Add new cells |
| `execute_cell(index)` | Run code cell and get output |
| `execute_python_code(code)` | Run arbitrary Python code |

### 3. Tool Execution Modes

Three modes for handling LLM tool calls:

| Mode | Behavior |
|------|----------|
| `manual` | User must approve each tool call |
| `auto` | Tools execute automatically (use with caution) |
| `ai_decide` | LLM decides based on operation risk |

### 4. Multi-Provider LLM Support

Seamlessly switch between AI providers per project:

```
┌─────────────────────────────────────────────────────────────────────┐
│                       LLM PROVIDERS                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐        │
│   │  Ollama  │   │  OpenAI  │   │ Anthropic│   │  Gemini  │        │
│   │ (Local)  │   │  GPT-4o  │   │  Claude  │   │  Google  │        │
│   └──────────┘   └──────────┘   └──────────┘   └──────────┘        │
│                                                                      │
│   Each project can use a different provider/model                   │
│   Provider can be switched at runtime                               │
└─────────────────────────────────────────────────────────────────────┘
```

### 5. Isolated Execution Environments

Each project gets its own Docker container:

```
Project A ──► playground-a1b2c3d4 ──► Dedicated Kernel + LLM Session
Project B ──► playground-e5f6g7h8 ──► Dedicated Kernel + LLM Session
Project C ──► playground-i9j0k1l2 ──► Dedicated Kernel + LLM Session
```

- Full isolation between users/projects
- Resource limits (CPU, memory)
- Auto-shutdown on idle timeout
- Containers can be restarted without data loss (S3 persistence)

---

## Workflow Illustrations

### User Workflow: Create and Use a Notebook

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         USER WORKFLOW                                       │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. REGISTER/LOGIN                                                          │
│     ┌────────┐      ┌──────────┐      ┌────────────┐                       │
│     │  User  │─────►│  Login   │─────►│  Dashboard │                       │
│     └────────┘      │  Page    │      │  (Projects)│                       │
│                     └──────────┘      └─────┬──────┘                       │
│                                             │                               │
│  2. CREATE PROJECT                          ▼                               │
│     ┌──────────────────────────────────────────────────────┐               │
│     │  Click "New Project" → Enter name → Project created  │               │
│     │  (Empty notebook stored in S3)                       │               │
│     └──────────────────────────────────────┬───────────────┘               │
│                                             │                               │
│  3. OPEN NOTEBOOK                           ▼                               │
│     ┌──────────────────────────────────────────────────────┐               │
│     │  Click project → Notebook Editor opens               │               │
│     │  Cells loaded from S3 via Master API                 │               │
│     └──────────────────────────────────────┬───────────────┘               │
│                                             │                               │
│  4. START PLAYGROUND                        ▼                               │
│     ┌──────────────────────────────────────────────────────┐               │
│     │  Click "Start Playground" → Docker container spins up │               │
│     │  Jupyter kernel starts, LLM session initialized      │               │
│     └──────────────────────────────────────┬───────────────┘               │
│                                             │                               │
│  5. WORK WITH AI                            ▼                               │
│     ┌──────────────────────────────────────────────────────┐               │
│     │  Chat: "Improve the function in cell 2"              │               │
│     │  ↓                                                    │               │
│     │  LLM calls: get_cell_content(2)                      │               │
│     │  LLM calls: update_cell_content(2, improved_code)    │               │
│     │  LLM calls: execute_cell(2)                          │               │
│     │  ↓                                                    │               │
│     │  Response: "I've improved and tested the function"   │               │
│     └──────────────────────────────────────────────────────┘               │
│                                                                             │
└────────────────────────────────────────────────────────────────────────────┘
```

### Chat with LLM: Tool Execution Flow

```
┌────────────────────────────────────────────────────────────────────────────┐
│                        CHAT TOOL EXECUTION FLOW                            │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────┐   1. Send message    ┌──────────────┐                         │
│  │  User   │ ─────────────────────►│   Frontend   │                         │
│  └─────────┘                       └──────┬───────┘                         │
│                                           │                                 │
│                                    2. Auto-save if dirty                    │
│                                           │                                 │
│                                    3. POST /api/projects/{id}/chat          │
│                                           ▼                                 │
│                                    ┌──────────────┐                         │
│                                    │  Master API  │                         │
│                                    └──────┬───────┘                         │
│                                           │                                 │
│                                    4. Forward to playground                 │
│                                           ▼                                 │
│                                    ┌──────────────┐                         │
│                                    │  Playground  │                         │
│                                    │  Container   │                         │
│                                    └──────┬───────┘                         │
│                                           │                                 │
│                                    5. LLM decides to use tools              │
│                                           │                                 │
│        ┌──────────────────────────────────┴──────────────────────────┐     │
│        │                                                              │     │
│        ▼                                                              ▼     │
│  ┌───────────────┐                                          ┌──────────────┐│
│  │ Tool Mode:    │                                          │ Tool Mode:   ││
│  │ MANUAL        │                                          │ AUTO         ││
│  └───────┬───────┘                                          └──────┬───────┘│
│          │                                                         │        │
│          ▼                                                         ▼        │
│  ┌───────────────────┐                                  ┌───────────────────┐│
│  │ Return pending    │                                  │ Execute tools     ││
│  │ tool calls to     │                                  │ immediately and   ││
│  │ user for approval │                                  │ return results    ││
│  └───────────────────┘                                  └───────────────────┘│
│                                                                             │
└────────────────────────────────────────────────────────────────────────────┘
```

### Lazy Load: How LLM Reads Notebook

```
┌────────────────────────────────────────────────────────────────────────────┐
│                  LLM TOOL: GET_CELL_CONTENT(2)                             │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌────────────┐                                                             │
│  │    LLM     │  1. Decides to read cell 2                                 │
│  │   Engine   │                                                             │
│  └─────┬──────┘                                                             │
│        │                                                                    │
│        ▼                                                                    │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │  tool_notebook_cells.py                                             │    │
│  │                                                                     │    │
│  │  def get_cell_content(cell_index: int):                            │    │
│  │      project_id = get_current_session().session_id                 │    │
│  │      return _call_master_api(                                       │    │
│  │          "GET",                                                     │    │
│  │          f"/internal/notebook/{project_id}/cell/{cell_index}"      │    │
│  │      )                                                              │    │
│  └───────────────────────────┬────────────────────────────────────────┘    │
│                              │                                              │
│                              ▼                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │  Master API: /internal/notebook/{project_id}/cell/2                │    │
│  │                                                                     │    │
│  │  1. Validate X-Internal-Secret header                              │    │
│  │  2. Load notebook from S3: notebooks/{project_id}/notebook.json    │    │
│  │  3. Extract cell at index 2                                        │    │
│  │  4. Return cell content                                            │    │
│  └───────────────────────────┬────────────────────────────────────────┘    │
│                              │                                              │
│                              ▼                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │  S3/MinIO                                                          │    │
│  │                                                                     │    │
│  │  notebooks/                                                        │    │
│  │    └── {project_id}/                                               │    │
│  │          └── notebook.json  ◄── Single Source of Truth            │    │
│  │                                                                     │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
ai_notebook_clone/
├── _source_project/          # Archived original vanilla JS project
│   ├── backend/              # Original Python backend
│   └── frontend/             # Original HTML/CSS/JS frontend
│
├── docs/                     # Documentation
│   ├── README.md             # This file
│   ├── DATABASE.md           # Database schema
│   ├── IMPLEMENTATION.md     # Implementation details
│   ├── IMPLEMENTATION_PLAN.md # Original planning doc
│   └── NOTEBOOK_LAZY_LOAD_ARCHITECTURE.md
│
├── infrastructure/           # Infrastructure services
│   ├── docker-compose.yml    # MySQL, Redis, MinIO
│   └── .env
│
├── master/                   # Master API (Control Plane)
│   ├── app/
│   │   ├── auth/             # JWT authentication
│   │   ├── users/            # User management
│   │   ├── projects/         # Project CRUD
│   │   ├── playgrounds/      # Container orchestration
│   │   ├── notebooks/        # S3 notebook storage
│   │   ├── chat/             # Chat history storage
│   │   └── internal/         # Internal API for playground
│   ├── Dockerfile
│   └── requirements.txt
│
├── playground/               # Playground Container Image
│   ├── backend/
│   │   ├── server.py         # FastAPI endpoints
│   │   ├── kernel_manager.py # Jupyter kernel
│   │   ├── session_manager.py # Session state
│   │   ├── llm_client.py     # Multi-provider LLM
│   │   └── llm_tools/        # Tool functions for LLM
│   │       ├── tool_notebook_cells.py
│   │       ├── tool_jupyter_kernel.py
│   │       ├── tool_file_utils.py
│   │       └── tool_terminal.py
│   ├── Dockerfile
│   └── requirements.txt
│
├── web/                      # Next.js Frontend
│   ├── src/
│   │   ├── app/
│   │   │   ├── auth/         # Login, Register
│   │   │   ├── dashboard/    # Project listing
│   │   │   └── notebook/[id] # Notebook editor
│   │   ├── components/
│   │   ├── lib/              # API client, stores
│   │   └── types/
│   ├── package.json
│   └── next.config.ts
│
├── nginx/                    # Reverse proxy config
│   └── nginx.conf
│
├── docker-compose.yml        # Orchestration shortcut
└── docker-compose.apps.yml   # Full stack compose
```

---

## API Endpoints

### Master API (External - User Facing)

```
Authentication:
  POST   /api/auth/register          Create account
  POST   /api/auth/login             Login (get JWT)
  POST   /api/auth/logout            Logout
  POST   /api/auth/refresh           Refresh token

Users:
  GET    /api/users/me               Current user info
  PATCH  /api/users/me               Update profile

Projects:
  GET    /api/projects               List projects
  POST   /api/projects               Create project
  GET    /api/projects/{id}          Get project
  PATCH  /api/projects/{id}          Update project
  DELETE /api/projects/{id}          Delete project

Notebooks:
  GET    /api/projects/{id}/notebook          Load notebook
  PUT    /api/projects/{id}/notebook          Save notebook
  GET    /api/projects/{id}/notebook/versions List versions
  POST   /api/projects/{id}/notebook/export   Export as .ipynb

Playgrounds:
  GET    /api/projects/{id}/playground        Status
  POST   /api/projects/{id}/playground/start  Start container
  POST   /api/projects/{id}/playground/stop   Stop container
  GET    /api/projects/{id}/playground/logs   Container logs
  POST   /api/projects/{id}/playground/activity Heartbeat

Chat:
  GET    /api/projects/{id}/chat              Get history
  POST   /api/projects/{id}/chat              Send message
  POST   /api/projects/{id}/chat/execute-tools Execute approved tools
  DELETE /api/projects/{id}/chat              Clear history
```

### Master API (Internal - Playground Facing)

```
Headers: X-Internal-Secret: {PLAYGROUND_INTERNAL_SECRET}

  GET    /api/internal/notebook/{id}/cells           Get all cells overview
  GET    /api/internal/notebook/{id}/cell/{index}    Get single cell
  PUT    /api/internal/notebook/{id}/cell/{index}    Update cell
  POST   /api/internal/notebook/{id}/cell/{position} Insert cell
  PUT    /api/internal/notebook/{id}/cell/{index}/output Update output
```

### Playground API (Container Internal)

```
  GET    /health                  Health check
  GET    /status                  Detailed status
  POST   /chat                    LLM chat
  POST   /chat/execute-tools      Execute tool calls
  POST   /llm/provider            Switch LLM provider
  GET    /llm/tool-mode           Get tool mode
  POST   /llm/tool-mode           Set tool mode
  WS     /ws/execute              Code execution streaming
```

---

## Known Limitations

### Current Limitations

| Limitation | Description | Workaround |
|------------|-------------|------------|
| No OAuth | Only email/password auth | Use strong passwords |
| No HTTPS | Running on HTTP in dev | Use nginx SSL in prod |
| Single region | No geo-replication | Deploy closer to users |
| No rate limiting | API calls not throttled | Implement in nginx |
| Manual LLM switch | Provider set per project | Use project settings |
| Container cold start | ~5-10s to start playground | Keep containers warm |

### Technical Constraints

| Constraint | Impact | Mitigation |
|------------|--------|------------|
| S3 latency | ~50-100ms per cell read | Batch reads where possible |
| Container memory | Default 2GB per playground | Configurable via env |
| Kernel state | Lost on container restart | Code persists in S3 |
| Chat history | Grows unbounded | Clear history periodically |

### Security Considerations

| Area | Status | Notes |
|------|--------|-------|
| JWT tokens | Implemented | 30min access, 7d refresh |
| Container isolation | Implemented | Docker network isolation |
| Internal API auth | Implemented | X-Internal-Secret header |
| Input sanitization | Partial | SQL injection protected |
| XSS prevention | Partial | React escaping |
| Rate limiting | Not implemented | Add nginx rate limits |

---

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Node.js 18+
- Python 3.10+ with Conda
- Ollama (for local LLM)

### 1. Start Infrastructure

```bash
cd infrastructure
docker-compose up -d
```

### 2. Build Playground Image

```bash
cd playground
docker build -t ainotebook-playground:latest .
```

### 3. Start Master API

```bash
cd master
conda activate ainotebook
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

### 4. Start Frontend

```bash
cd web
npm install
npm run dev
```

### 5. Access Application

- Frontend: http://localhost:3000
- Master API Docs: http://localhost:8001/docs
- MinIO Console: http://localhost:9003

### Alternative: Full Stack with Docker Compose

```bash
docker-compose -f docker-compose.apps.yml up --build
```

---

## Environment Variables

See individual service `.env` files:
- `infrastructure/.env` - MySQL, Redis, MinIO credentials
- `master/.env` - API settings, JWT secret, S3 config
- `playground` - Uses runtime env from Master API

---

## Related Documentation

- [Database Schema](DATABASE.md) - Table definitions, relationships
- [Implementation Details](IMPLEMENTATION.md) - Technical decisions, code patterns
- [Lazy Load Architecture](NOTEBOOK_LAZY_LOAD_ARCHITECTURE.md) - LLM tool data flow
- [Implementation Plan](IMPLEMENTATION_PLAN.md) - Original planning document

---

## Contributing

This is a personal project. For questions or suggestions, please open an issue.

## License

Private/Internal Use
