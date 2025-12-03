# AI Cell Implementation

## Overview

A new **AI Cell** type that allows users to interact with the LLM inline within the notebook, without using the chat panel. The AI cell understands the entire notebook context (all cells above and below) and can respond with code, text, or explanations.

**Status: IMPLEMENTED**

## Cell Structure

### Storage Format (in notebook.json)

```json
{
  "id": "cell-uuid-here",
  "cell_type": "ai",
  "metadata": {
    "ai_cell": true
  },
  "source": "",
  "ai_data": {
    "user_prompt": "Explain what the dataframe contains and suggest visualizations",
    "llm_response": "Based on your DataFrame `df`, it contains...",
    "llm_model": "gemini-2.0-flash",
    "status": "completed",
    "timestamp": "2024-01-15T10:30:00Z",
    "actions": [
      {
        "type": "code_suggestion",
        "content": "import matplotlib.pyplot as plt\nplt.figure(figsize=(10,6))..."
      }
    ]
  }
}
```

### Status Values
- `idle` - No prompt yet or cleared
- `running` - LLM is processing
- `completed` - Response received
- `error` - LLM error occurred

## UI Design

```
┌─────────────────────────────────────────────────────────────────┐
│ [AI] ✨                                            [▶ Run] [🗑] │
├─────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ 💬 Your prompt:                                             │ │
│ │ ┌─────────────────────────────────────────────────────────┐ │ │
│ │ │ Explain what the dataframe contains and suggest        │ │ │
│ │ │ visualizations I can create with this data.            │ │ │
│ │ └─────────────────────────────────────────────────────────┘ │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                 │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ 🤖 AI Response:                                    [Copy]   │ │
│ │ ─────────────────────────────────────────────────────────── │ │
│ │ Based on your DataFrame `df`, it contains 3 columns:       │ │
│ │                                                             │ │
│ │ - **date**: Transaction dates                               │ │
│ │ - **amount**: Numeric values (likely currency)              │ │
│ │ - **category**: Categorical labels                          │ │
│ │                                                             │ │
│ │ Here are some visualization suggestions:                    │ │
│ │                                                             │ │
│ │ ```python                                     [Insert ↓]    │ │
│ │ import matplotlib.pyplot as plt                             │ │
│ │ df.groupby('category')['amount'].sum().plot(kind='bar')     │ │
│ │ plt.title('Total by Category')                              │ │
│ │ plt.show()                                                  │ │
│ │ ```                                                         │ │
│ │                                                             │ │
│ │ 📊 Model: gemini-2.0-flash | ⏱ 2.3s                        │ │
│ └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Key UI Features

1. **Prompt Input Area**
   - Editable textarea for user's question
   - Placeholder: "Ask AI about your notebook..."
   - Supports multi-line input

2. **Run Button**
   - Executes the AI prompt
   - Shows loading spinner while processing
   - Keyboard shortcut: Shift+Enter

3. **Response Area**
   - Rendered markdown
   - Code blocks with syntax highlighting
   - "Insert Below" button on code blocks → inserts as new code cell
   - "Copy" button for easy copying

4. **Cell Actions**
   - Re-run with modified prompt
   - Clear response
   - Delete cell

## Architecture

### Frontend Components

```
web/src/components/notebook/
├── Cell.tsx                    # Existing - add AI cell type routing
├── AICell.tsx                  # NEW - Main AI cell component
├── AICellPromptInput.tsx       # NEW - Prompt textarea
└── AICellResponse.tsx          # NEW - Response renderer with actions
```

### Backend Flow

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Frontend   │────▶│   Master     │────▶│  Playground  │
│   AICell     │     │   API        │     │   LLM        │
└──────────────┘     └──────────────┘     └──────────────┘
       │                    │                    │
       │ 1. User types      │                    │
       │    prompt &        │                    │
       │    clicks Run      │                    │
       │                    │                    │
       │ 2. POST /ai-cell   │                    │
       │    with prompt +   │                    │
       │    all cell IDs    │                    │
       │───────────────────▶│                    │
       │                    │                    │
       │                    │ 3. Forward to      │
       │                    │    playground      │
       │                    │    with context    │
       │                    │───────────────────▶│
       │                    │                    │
       │                    │                    │ 4. Build context
       │                    │                    │    from ALL cells
       │                    │                    │    (no tools, just
       │                    │                    │    question mode)
       │                    │                    │
       │                    │◀───────────────────│ 5. LLM response
       │◀───────────────────│                    │
       │                    │                    │
       │ 6. Render response │                    │
       │    + save to cell  │                    │
```

### API Endpoints

#### Master API

```python
# POST /internal/notebook/{project_id}/ai-cell/run
class AICellRunRequest(BaseModel):
    cell_id: str           # The AI cell's ID
    prompt: str            # User's question
    cell_ids: List[str]    # All notebook cell IDs for context

class AICellRunResponse(BaseModel):
    success: bool
    response: str          # LLM's markdown response
    model: str             # Which model was used
    error: Optional[str]
```

#### Playground API

```python
# POST /ai-cell/run
# Similar to chat but:
# - No tool calling (pure question/answer)
# - Returns complete response (not streaming for now)
# - System prompt tailored for notebook analysis
```

## Implementation Steps

### Phase 1: Backend Infrastructure

1. **Master API** (`master/app/internal/routes.py`)
   - Add AI cell run endpoint
   - Forward to playground service

2. **Playground API** (`playground/backend/server.py`)
   - Add `/ai-cell/run` endpoint
   - Create simplified LLM call (no tools)

3. **AI Cell System Prompt** (`playground/backend/llm_client_base.py`)
   - Create `get_ai_cell_system_prompt()` method
   - Tailored for notebook analysis without tool use

### Phase 2: Frontend - Cell Type

4. **Cell Type Definition** (`web/src/types/notebook.ts`)
   - Add 'ai' to cell_type union
   - Define AIData interface

5. **Cell Router** (`web/src/components/notebook/Cell.tsx`)
   - Add case for 'ai' cell type
   - Render AICell component

6. **AICell Component** (`web/src/components/notebook/AICell.tsx`)
   - Prompt input with textarea
   - Run button with loading state
   - Response display area

### Phase 3: Frontend - Response Features

7. **Response Renderer** (`web/src/components/notebook/AICellResponse.tsx`)
   - Markdown rendering
   - Code block extraction
   - "Insert as Cell" functionality

8. **Toolbar Update** (`web/src/components/notebook/NotebookToolbar.tsx`)
   - Add "AI Cell" button to insert new AI cells

### Phase 4: Persistence

9. **Save/Load AI Cells**
   - Ensure ai_data is saved to notebook.json
   - Load and restore AI cell state

### Phase 5: Polish

10. **Keyboard Shortcuts**
    - Shift+Enter to run
    - Escape to cancel

11. **Streaming (Optional)**
    - Stream LLM response for better UX

## System Prompt for AI Cell

```
You are an AI assistant embedded in a Jupyter-like notebook. The user is asking
a question about their notebook code and data.

CONTEXT:
You have access to the entire notebook content shown below. Analyze all cells
(code, markdown, outputs) to understand what the user is working on.

GUIDELINES:
- Be concise but thorough
- When suggesting code, make it ready to run
- Reference specific cells or variables by name
- If asked to generate code, wrap it in ```python blocks
- You can see cell outputs including DataFrames, plots, and errors

NOTEBOOK CONTENT:
{full_notebook_context}

USER QUESTION:
{user_prompt}
```

## Key Differences from Chat Panel

| Feature | Chat Panel | AI Cell |
|---------|------------|---------|
| Location | Side panel | Inline in notebook |
| Tool Use | Yes (can modify cells) | No (read-only analysis) |
| Context | Tiered (overview + tools) | Full notebook content |
| History | Conversation thread | Single Q&A per cell |
| Use Case | Complex tasks, edits | Quick questions, explanations |

## Future Enhancements

1. **Tool Mode (v2)** - Option to enable tools so AI cell can insert/modify cells
2. **Streaming** - Real-time response streaming
3. **Multiple Models** - Dropdown to select model per AI cell
4. **Cell References** - @mention syntax to reference specific cells
5. **Voice Input** - Speech-to-text for prompts
