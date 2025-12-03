# Context Management for AI Chat

This document explains how notebook context is passed to the LLM during chat interactions.

## Overview

The system uses a **tiered context approach** to minimize token usage while giving the LLM full awareness of the notebook.

- **Tier 1**: Compact overview (always sent) - ~500 tokens
- **Tier 2**: Full cell content (fetched on-demand via tools)

## Flow

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Frontend   │────▶│   Backend    │────▶│   Context    │────▶│     LLM      │
│  (React UI)  │     │  (FastAPI)   │     │   Manager    │     │              │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
       │                    │                    │                    │
       │ 1. Auto-save       │                    │                    │
       │    if dirty        │                    │                    │
       │                    │                    │                    │
       │ 2. Send ALL        │                    │                    │
       │    cell IDs        │                    │                    │
       │───────────────────▶│                    │                    │
       │                    │ 3. Load cells      │                    │
       │                    │    from S3         │                    │
       │                    │───────────────────▶│                    │
       │                    │                    │ 4. Create          │
       │                    │                    │    compact         │
       │                    │                    │    overview        │
       │                    │                    │───────────────────▶│
       │                    │                    │                    │
       │                    │                    │    5. LLM uses     │
       │                    │                    │◀───────────────────│
       │                    │                    │    tools for       │
       │                    │                    │    details         │
```

## Context Format

The LLM receives a compact overview:

```
=== NOTEBOOK OVERVIEW ===
Total cells: 5
Imports: pandas, numpy, matplotlib
Variables: df:DataFrame, model:RandomForestClassifier()

[ERRORS]
  cell-abc123: KeyError: 'missing_column'

[CELLS]
ID              | Type | Preview                        | Output
-----------------------------------------------------------------
cell-1a2b3c...  | py   | import pandas as pd            |
cell-4d5e6f...  | py   | df = pd.read_csv('data.csv')   | [DataFrame]
cell-abc123...  | py   | df.groupby('category').sum()   | [ERROR]
cell-7g8h9i...  | md   | # Analysis Results             |
cell-jklmno...  | py   | plt.plot(df['x'], df['y'])     | [image]

=== END OVERVIEW ===

Use get_cell_content(cell_id) to read full cell content/output.
```

## Key Features

### Auto-Include All Cells
- No manual cell selection required
- All cells are automatically included in context
- Frontend sends all cell IDs to backend

### Auto-Save Before Chat
- If notebook has unsaved changes (`isDirty`), it's saved before sending to LLM
- Ensures LLM always sees the latest state

### Stable Cell IDs
- Uses `cell_id` (UUID) instead of cell numbers
- Cell IDs don't change when cells are inserted/deleted
- LLM uses cell IDs for all tool operations

### Extracted Metadata
- **Imports**: Libraries already imported (LLM won't re-import)
- **Variables**: Defined variables with inferred types
- **Errors**: Recent errors with cell IDs for quick fixes

## LLM Tools

The LLM can fetch details using these tools:

| Tool | Purpose |
|------|---------|
| `get_cell_content(cell_id)` | Get full content + output of a cell |
| `get_notebook_overview()` | Refresh cell list |
| `update_cell_content(...)` | Modify cell code |
| `insert_cell(...)` | Add new cell |
| `execute_cell(cell_id)` | Run a cell |
| `execute_python_code(code)` | Run arbitrary Python |

## Files

| File | Description |
|------|-------------|
| `playground/backend/context_manager.py` | Creates tiered context from cells |
| `playground/backend/llm_client_base.py` | System prompt with context instructions |
| `web/src/app/notebook/[id]/page.tsx` | Frontend - sends all cell IDs |

## Benefits

| Before (Manual Selection) | After (Auto + Tiered) |
|---------------------------|----------------------|
| User selects cells manually | All cells auto-included |
| Risk of missing context | Full notebook awareness |
| ~2000 tokens per cell | ~500 tokens for overview |
| Cell numbers (unstable) | Cell IDs (stable) |
