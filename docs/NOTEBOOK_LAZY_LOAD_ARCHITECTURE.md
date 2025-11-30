# Notebook Lazy Load Architecture

## Overview

This document describes the architecture for how LLM tools access notebook data in the AI Notebook platform. We use a **Lazy Load** approach where the Playground's LLM tools fetch notebook data on-demand from the Master API (which reads from S3/MinIO).

## Why Lazy Load?

### Previous Approach: Full Sync (Problematic)

```
Frontend ──► Master API ──► Playground
           (sync all cells)

Problems:
- 100 cells × 500 chars = 50KB per sync
- Sync on: page load, save, before chat
- Wasteful: 99 cells didn't change
- Two sources of truth (S3 + Playground memory)
- Sync conflicts possible
```

### Current Approach: Lazy Load (Recommended)

```
Frontend ──► Master API ──► S3/MinIO (SINGLE SOURCE OF TRUTH)
                 ▲
                 │ API calls (on-demand)
                 │
            Playground
            (LLM tools fetch when needed)

Benefits:
- Zero pre-sync overhead
- LLM only fetches cells it needs
- Single source of truth (S3)
- No sync conflicts
- Stateless playground
```

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA FLOW                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                         FRONTEND (Next.js)                            │  │
│  │                                                                       │  │
│  │  User Actions:                                                        │  │
│  │  - Edit cells (local state)                                          │  │
│  │  - Save notebook (POST /api/projects/{id}/notebook)                  │  │
│  │  - Send chat (POST /api/projects/{id}/chat)                          │  │
│  │                                                                       │  │
│  │  Note: Auto-save before chat ensures LLM sees latest edits           │  │
│  └───────────────────────────────────┬──────────────────────────────────┘  │
│                                      │                                      │
│                                      ▼                                      │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                       MASTER API (FastAPI)                            │  │
│  │                                                                       │  │
│  │  External Endpoints (user-facing):                                   │  │
│  │  - GET  /api/projects/{id}/notebook         → Load notebook          │  │
│  │  - PUT  /api/projects/{id}/notebook         → Save notebook          │  │
│  │  - POST /api/projects/{id}/chat             → Send chat message      │  │
│  │                                                                       │  │
│  │  Internal Endpoints (playground-facing):                             │  │
│  │  - GET  /internal/notebook/{id}/cells       → Get all cells          │  │
│  │  - GET  /internal/notebook/{id}/cell/{idx}  → Get single cell        │  │
│  │  - PUT  /internal/notebook/{id}/cell/{idx}  → Update cell            │  │
│  │  - POST /internal/notebook/{id}/cell        → Insert cell            │  │
│  │                                                                       │  │
│  └───────────────────────────────────┬──────────────────────────────────┘  │
│                                      │                                      │
│                    ┌─────────────────┴─────────────────┐                   │
│                    │                                   │                   │
│                    ▼                                   ▼                   │
│  ┌────────────────────────────────┐  ┌────────────────────────────────┐   │
│  │        S3/MinIO Storage        │  │     Playground Container       │   │
│  │                                │  │                                │   │
│  │  notebooks/{user}/{project}/   │  │  LLM Tools:                   │   │
│  │    notebook.json               │  │  - get_notebook_overview()    │   │
│  │    versions/                   │  │  - get_cell_content(idx)      │   │
│  │      v1.json                   │  │  - update_cell_content()      │   │
│  │      v2.json                   │  │  - insert_cell()              │   │
│  │                                │  │  - execute_cell()             │   │
│  │  SINGLE SOURCE OF TRUTH        │  │                                │   │
│  │                                │  │  All tools call Master API    │   │
│  └────────────────────────────────┘  │  to read/write notebook data  │   │
│                                      │                                │   │
│                                      │  Jupyter Kernel:              │   │
│                                      │  - Executes code cells        │   │
│                                      │  - Returns output             │   │
│                                      └────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## LLM Tool Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    EXAMPLE: LLM READS CELL CONTENT                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. User asks: "What does cell 3 do?"                                      │
│                                                                             │
│  2. LLM decides to call get_cell_content(3)                                │
│                                                                             │
│  3. Tool implementation:                                                    │
│     ┌─────────────────────────────────────────────────────────────────┐    │
│     │  def get_cell_content(cell_index: int):                         │    │
│     │      # Get project_id from current session                      │    │
│     │      session = get_current_session()                            │    │
│     │      project_id = session.project_id                            │    │
│     │                                                                  │    │
│     │      # Fetch from Master API                                    │    │
│     │      response = httpx.get(                                      │    │
│     │          f"{MASTER_API_URL}/internal/notebook/{project_id}/cell/{cell_index}",│
│     │          headers={"X-Internal-Secret": INTERNAL_SECRET}         │    │
│     │      )                                                           │    │
│     │                                                                  │    │
│     │      return response.json()                                     │    │
│     └─────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  4. Master API loads cell from S3 and returns it                           │
│                                                                             │
│  5. LLM receives cell content and responds to user                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Auto-Save Before Chat

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      AUTO-SAVE FLOW                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  User clicks "Send" on chat message:                                       │
│                                                                             │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌──────────┐  │
│  │   Check if  │ YES │  Auto-save  │     │  Send chat  │     │   LLM    │  │
│  │   dirty?    │────►│  notebook   │────►│   message   │────►│ processes│  │
│  │             │     │   to S3     │     │             │     │          │  │
│  └──────┬──────┘     └─────────────┘     └─────────────┘     └──────────┘  │
│         │ NO                                                                │
│         └───────────────────────────────────►                              │
│                                                                             │
│  This ensures LLM always sees the latest edits when using tools.           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Session Management

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      SESSION STATE (Simplified)                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Before (with sync):                                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Session {                                                          │   │
│  │    session_id: "project-uuid",                                      │   │
│  │    kernel: NotebookKernel,                                          │   │
│  │    notebook_cells: [...],  ◄── REMOVED (was synced copy)           │   │
│  │    notebook_updates: [...], ◄── REMOVED                            │   │
│  │    pending_client: LLMClient,                                       │   │
│  │  }                                                                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  After (lazy load):                                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Session {                                                          │   │
│  │    session_id: "project-uuid",                                      │   │
│  │    project_id: "project-uuid",  ◄── Used by tools to call API      │   │
│  │    kernel: NotebookKernel,                                          │   │
│  │    pending_client: LLMClient,                                       │   │
│  │  }                                                                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  Note: notebook_state.py becomes mostly unused or simplified               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Files Affected

| File | Changes |
|------|---------|
| `playground/backend/tool_notebook_cells.py` | Rewrite to call Master API |
| `playground/backend/notebook_state.py` | Remove or simplify (no longer stores cells) |
| `playground/backend/session_manager.py` | Remove notebook_cells, add project_id |
| `playground/backend/server.py` | Remove /notebook/sync endpoint |
| `master/app/notebooks/routes.py` | Add internal endpoints, remove /sync |
| `master/app/notebooks/schemas.py` | Remove NotebookSyncRequest |
| `web/src/lib/api.ts` | Remove syncToPlayground, add auto-save logic |
| `web/src/app/notebook/[id]/page.tsx` | Remove sync calls, add auto-save before chat |

## Internal API Authentication

```
Playground ──► Master API

Headers:
  X-Internal-Secret: {PLAYGROUND_INTERNAL_SECRET}

The Master API validates this secret for /internal/* endpoints.
This prevents unauthorized access to internal endpoints.
```

## Benefits Summary

| Aspect | Before (Full Sync) | After (Lazy Load) |
|--------|-------------------|-------------------|
| Data consistency | Two copies, can drift | Single source (S3) |
| Network overhead | 50KB+ per sync | Only what's needed |
| Sync timing | Manual (error-prone) | Not needed |
| Conflict resolution | Complex | None (save → read) |
| Playground state | Stateful (cells in memory) | Stateless |
| Container restart | Loses synced data | No data to lose |

## Migration Notes

1. Existing notebooks in S3 remain unchanged
2. No database migrations needed
3. Frontend save flow remains the same
4. Chat history flow remains the same
5. Only LLM tool implementation changes
