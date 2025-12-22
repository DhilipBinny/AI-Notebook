# Playground Backend Architecture

The Playground is a FastAPI-based headless server that provides isolated Jupyter kernel execution and LLM integration for each notebook project.

---

## Overview

```
+------------------------------------------------------------------+
|                      PLAYGROUND CONTAINER                         |
+------------------------------------------------------------------+
|                                                                    |
|  +-------------------+    +-------------------+    +------------+  |
|  |   FastAPI Server  |    |  Session Manager  |    |   Kernel   |  |
|  |                   |<-->|                   |<-->|   Manager  |  |
|  |  - Routes         |    |  - Per-project    |    |            |  |
|  |  - SSE Streaming  |    |  - Thread-safe    |    |  - Jupyter |  |
|  |  - Auth           |    |  - Lazy loading   |    |  - Python  |  |
|  +-------------------+    +-------------------+    +------------+  |
|           |                                                        |
|           v                                                        |
|  +-------------------+    +-------------------+                    |
|  |   LLM Clients     |    |   Context Manager |                    |
|  |                   |    |                   |                    |
|  |  - Gemini         |    |  - XML/JSON/Plain |                    |
|  |  - Anthropic      |    |  - Tiered context |                    |
|  |  - OpenAI         |    |  - Token efficient|                    |
|  |  - Ollama         |    +-------------------+                    |
|  +-------------------+                                             |
|           |                                                        |
|           v                                                        |
|  +----------------------------------------------------------+     |
|  |                      LLM TOOLS (25)                       |     |
|  |                                                           |     |
|  |  Kernel: execute_python_code                              |     |
|  |  Cells:  get_notebook_overview, get_cell_content, ...     |     |
|  |  Files:  list_project_files, read_text_file, ...          |     |
|  |  Pip:    pip_install, pip_list, ...                       |     |
|  |  Runtime: runtime_list_variables, runtime_get_dataframe...|     |
|  |  Sandbox: sandbox_execute, sandbox_reset, ...             |     |
|  +----------------------------------------------------------+     |
|                                                                    |
+------------------------------------------------------------------+
```

---

## API Endpoints

### Health & Status

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Basic health check (no auth) |
| `/status` | GET | Detailed status with session count |

### Session Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/session/create` | POST | Create new session with isolated kernel |
| `/session/{id}` | GET | Get session information |
| `/session/{id}` | DELETE | Delete session and cleanup |
| `/session/` | GET | List all active sessions |
| `/session/{id}/kernel/start` | POST | Start kernel |
| `/session/{id}/kernel/stop` | POST | Stop kernel |
| `/session/{id}/kernel/restart` | POST | Restart kernel |
| `/session/{id}/kernel/interrupt` | POST | Interrupt execution |
| `/session/{id}/kernel/status` | GET | Get kernel status |

### Code Execution

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/execute` | POST | Execute code and get results |
| `/ws/execute` | WebSocket | Streaming execution with real-time output |

### AI Cell (SSE Streaming)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ai-cell/run` | POST | Execute AI Cell with LLM + tools (SSE) |
| `/ai-cell/cancel` | POST | Cancel running AI Cell |

**SSE Events:**
```
thinking     -> {"message": "Analyzing..."}
tool_call    -> {"name": "execute_python_code", "args": {...}}
tool_result  -> {"name": "execute_python_code", "result": "..."}
done         -> {"success": true, "response": "...", "steps": [...]}
error        -> {"error": "..."}
```

### Chat Panel (SSE Streaming)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chat/stream` | POST | Chat with LLM + tool execution (SSE) |
| `/chat/execute-tools/stream` | POST | Execute approved tools (SSE) |

**SSE Events:**
```
thinking       -> {"message": "Processing your request..."}
tool_call      -> {"name": "update_cell_content", "arguments": {...}}
tool_result    -> {"name": "update_cell_content", "result": "..."}
pending_tools  -> {"tools": [...]}  (manual mode only)
done           -> {"success": true, "response": "...", "pending_tool_calls": [...]}
error          -> {"error": "..."}
```

### LLM Completion

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/llm/complete` | POST | Simple text completion (no tools) |

---

## LLM Providers

### Supported Providers

| Provider | Default Model | Key Features |
|----------|---------------|--------------|
| **Gemini** | gemini-2.0-flash-exp | Google Search grounding, multimodal, automatic caching |
| **Anthropic** | claude-sonnet-4-20250514 | Prompt caching, multimodal, extended thinking |
| **OpenAI** | gpt-4o | Vision, function calling |
| **Ollama** | qwen3-coder:30b | Local execution, no API key needed |

### Provider Switching

Providers can be switched at runtime via the `llm_provider` parameter in chat/AI cell requests.

### Web Search Integration

Each provider uses its native web search:
- **Gemini**: Google Search (grounding)
- **Anthropic**: Brave Search (via tool)
- **OpenAI**: Bing Search (via tool)
- **Ollama**: DuckDuckGo (via tool)

**Weighted Detection System:**
```
Score = keyword_weight + time_sensitivity + question_pattern

Keywords: "latest", "current", "news", "price" -> +0.3 each
Time: "today", "2024", "this week" -> +0.4
Questions: "what is", "how much" -> +0.2

Threshold: 0.5 (search if score >= 0.5)
```

---

## LLM Tools

### Tool Sets

| Set | Count | Usage |
|-----|-------|-------|
| `TOOL_FUNCTIONS` | 25 | Chat Panel - full access |
| `AI_CELL_TOOLS` | 10 | AI Cell - read-only + sandbox |

### Complete Tool Reference

#### Kernel Execution
| Tool | Description |
|------|-------------|
| `execute_python_code(code)` | Execute Python in user's kernel (output NOT saved to cells) |

#### Notebook Cell Operations
| Tool | Description |
|------|-------------|
| `get_notebook_overview(detail)` | Get all cells with IDs ("brief" or "full") |
| `get_cell_content(cell_id)` | Get specific cell content by ID |
| `update_cell_content(cell_id, content)` | Edit cell content |
| `delete_cell(cell_id)` | Delete a cell |
| `multi_delete_cells(cell_ids)` | Delete multiple cells |
| `multi_insert_cells(cells, position)` | Insert multiple cells at position |
| `insert_cell_after(cell_id, type, content)` | Insert after specific cell |
| `insert_cell_at_position(index, type, content)` | Insert at position |
| `execute_cell(cell_id)` | Execute cell and update outputs |

#### File Operations
| Tool | Description |
|------|-------------|
| `list_project_files(path, pattern, recursive)` | List files with glob patterns |
| `file_info(path)` | Get file metadata (size, modified, type) |
| `read_text_file(path, max_lines)` | Read text file content |
| `preview_data_file(path, rows)` | Preview CSV/Excel without full load |
| `write_text_file(path, content, overwrite)` | Write/create text files |
| `delete_file(path, confirm)` | Delete files |

**Security:** All paths restricted to project directory with symlink protection.

#### Package Management
| Tool | Description |
|------|-------------|
| `pip_install(packages, upgrade)` | Install packages in kernel environment |
| `pip_uninstall(packages)` | Uninstall packages |
| `pip_list()` | List installed packages |
| `pip_show(package)` | Show package details |
| `pip_search_installed(query)` | Search installed packages |
| `extract_missing_modules(error_message)` | Parse ImportError for missing modules |

#### Runtime Inspection (Requires Running Kernel)
| Tool | Description |
|------|-------------|
| `runtime_list_variables()` | List all variables with types, shapes, previews |
| `runtime_get_variable(name)` | Get specific variable value |
| `runtime_get_dataframe(name, rows)` | Get DataFrame preview (head/tail/info) |
| `runtime_list_functions()` | List user-defined functions |
| `runtime_list_imports()` | List imported modules |
| `runtime_kernel_status()` | Get kernel info (memory, execution count) |
| `runtime_get_last_error()` | Get last execution error |

#### Sandbox Testing (Isolated Kernel)
| Tool | Description |
|------|-------------|
| `sandbox_execute(code, timeout)` | Test code in isolated environment (default 10s) |
| `sandbox_reset()` | Reset sandbox kernel |
| `sandbox_pip_install(packages)` | Install packages in sandbox |
| `sandbox_sync_from_main(variable_names)` | Copy variables from main kernel |
| `sandbox_status()` | Get sandbox kernel status |

---

## Tool Execution Modes

| Mode | Behavior |
|------|----------|
| `auto` | LLM executes tools automatically in loop (up to MAX_TOOL_ITERATIONS) |
| `manual` | Returns pending tools for user approval via UI |
| `ai_decide` | Smart validator decides which tools need approval |

### Tool Execution Flow

```
           +------------------+
           |   User Message   |
           +--------+---------+
                    |
                    v
           +------------------+
           |   LLM Analysis   |
           +--------+---------+
                    |
        +-----------+-----------+
        |           |           |
        v           v           v
    +-------+   +-------+   +----------+
    | auto  |   |manual |   |ai_decide |
    +---+---+   +---+---+   +----+-----+
        |           |            |
        v           v            v
    Execute     Return       Validator
    Tools       Pending      Decides
    Loop        Tools        +-------+
        |           |        |       |
        v           v        v       v
    +-------+   +-------+  safe   unsafe
    | Done  |   | User  |    |       |
    +-------+   |Approve|    v       v
                +---+---+ Execute  Return
                    |     Loop    Pending
                    v
                Execute
                Tools
```

---

## Session Management

### Lazy Kernel Architecture

```
BEFORE (blocking):
  Request -> Create Kernel -> Call LLM -> Execute Tools
              (slow!)

AFTER (parallel OK):
  Request -> Set Session ID -> Call LLM -> [Tools need kernel?] -> Create on demand
              (instant)        (parallel)        (lazy)
```

**Benefits:**
- Multiple LLM queries run in parallel
- Kernel only created when tools actually need it
- "What can you do?" queries respond immediately

### Session Structure

```python
Session = {
    session_id: str,           # Usually = project_id
    kernel: NotebookKernel,    # Isolated Jupyter kernel
    notebook_name: str,        # Associated notebook
    pending_client: LLMClient, # For tool approval flow
    llm_steps: List[LLMStep],  # Tool call history
    created_at: datetime,
    last_activity: datetime,
}
```

### Thread Safety

- Uses `contextvars` for concurrent request support
- Each request gets isolated context
- Session-level operations protected by locks

---

## Context Management

### Tiered Context Approach

```
+------------------------------------------------------------------+
|                    TIERED CONTEXT SYSTEM                          |
+------------------------------------------------------------------+
|                                                                    |
|  TIER 1 (Always Included - Minimal Tokens):                       |
|  +------------------------------------------------------------+   |
|  | - Imports from all cells                                    |   |
|  | - Variable names and types                                  |   |
|  | - Recent errors                                             |   |
|  | - Cell overview (ID, type, 60-char preview)                |   |
|  +------------------------------------------------------------+   |
|                                                                    |
|  TIER 2 (On-Demand via Tools):                                    |
|  +------------------------------------------------------------+   |
|  | - Full cell content via get_cell_content(cell_id)          |   |
|  | - Variable values via runtime_get_variable(name)           |   |
|  | - DataFrame previews via runtime_get_dataframe(name)       |   |
|  +------------------------------------------------------------+   |
|                                                                    |
|  Result: ALL cells in context with MINIMAL token usage            |
+------------------------------------------------------------------+
```

### Format Options

| Format | Best For | Features |
|--------|----------|----------|
| `xml` | Claude/Anthropic | 40% accuracy boost, trained on XML tags |
| `json` | OpenAI/Gemini | Structured parsing, standard format |
| `plain` | Ollama/Local | Simple text, lower overhead |

### Caching Strategy

```
notebook_context (cacheable)     +  user_prompt (never cached)
      |                                      |
      v                                      v
[System + Tier 1 Context]        [User's actual question]
      |                                      |
      +---> Anthropic: cache_control         |
      +---> Gemini: automatic caching        |
      +---> OpenAI: standard                 |
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | gemini | Default provider (gemini/anthropic/openai/ollama) |
| `TOOL_EXECUTION_MODE` | manual | Tool mode (auto/manual/ai_decide) |
| `MAX_TOOL_ITERATIONS` | 10 | Maximum tool execution loop iterations |
| `ENABLE_WEB_SEARCH` | true | Enable provider web search |
| `CONTEXT_FORMAT` | xml | Context format (xml/json/plain) |
| `AI_CELL_STREAMING_ENABLED` | true | Enable SSE streaming for AI cells |

### Provider-Specific

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | Google AI API key |
| `GEMINI_MODEL` | Model name (default: gemini-2.0-flash-exp) |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `ANTHROPIC_MODEL` | Model name (default: claude-sonnet-4-20250514) |
| `OPENAI_API_KEY` | OpenAI API key |
| `OPENAI_MODEL` | Model name (default: gpt-4o) |
| `OLLAMA_URL` | Ollama server URL (default: http://localhost:11434) |
| `OLLAMA_MODEL` | Model name (default: qwen3-coder:30b) |

### Integration

| Variable | Description |
|----------|-------------|
| `MASTER_API_URL` | Master API URL for notebook data |
| `INTERNAL_SECRET` | Auth token for internal API calls |
| `MINIO_DATA_PATH` | Local project data mount path |

---

## Security

### Authentication
- Internal secret header (`X-Internal-Secret`) for Master API calls
- Session isolation per project

### File System
- All file operations restricted to project directory
- Path traversal prevention
- Symlink attack protection

### Kernel Isolation
- Each project gets dedicated Docker container
- Separate Jupyter kernel per session
- Resource limits (CPU, memory) configurable

---

## Data Flow Examples

### Chat with Auto Tool Execution

```
1. User sends: "Add a function to calculate factorial in cell 3"
   |
2. Frontend auto-saves notebook (if dirty)
   |
3. POST /chat/stream with SSE
   |
4. Playground:
   a. Set session ID (lazy kernel)
   b. Build tiered context
   c. Send to LLM with tools
   |
5. LLM decides to call tools:
   <- SSE: thinking {"message": "Processing..."}
   <- SSE: tool_call {"name": "get_cell_content", "arguments": {"cell_id": "cell-3"}}
   <- SSE: tool_result {"name": "get_cell_content", "result": "..."}
   <- SSE: tool_call {"name": "update_cell_content", "arguments": {...}}
   <- SSE: tool_result {"name": "update_cell_content", "result": "success"}
   |
6. Final response:
   <- SSE: done {"success": true, "response": "I've added the factorial function..."}
```

### AI Cell Inline Query

```
1. User types in AI cell: "What variables are defined?"
   |
2. POST /ai-cell/run with SSE
   |
3. Playground:
   a. Set session ID (lazy kernel)
   b. Build positional context (AI cell location)
   c. Send to LLM with AI_CELL_TOOLS subset
   |
4. LLM calls runtime inspection:
   <- SSE: thinking {"message": "Starting AI analysis..."}
   <- SSE: tool_call {"name": "runtime_list_variables"}
   <- SSE: tool_result {"name": "runtime_list_variables", "result": "[...]"}
   |
5. Final response:
   <- SSE: done {"success": true, "response": "You have 3 variables defined: df (DataFrame), x (int), y (str)"}
```

---

## Performance Optimizations

### Lazy Kernel Loading
- Kernel created only when tools need execution
- Parallel LLM requests for queries without tools

### Tiered Context
- Minimal tokens in initial context
- Full content fetched on-demand

### SSE Streaming
- Real-time progress updates
- No blocking on long operations

### Provider Caching
- Anthropic: Explicit cache_control
- Gemini: Automatic caching
- Reduces token costs on repeated context

---

## Monitoring

### Health Endpoints

```bash
# Basic health
curl http://localhost:8080/health
# {"status": "ok"}

# Detailed status (requires auth)
curl -H "X-Internal-Secret: xxx" http://localhost:8080/status
# {"status": "ok", "sessions": 2, "uptime": 3600}
```

### Kernel Status

```bash
GET /session/{id}/kernel/status
# {"status": "idle", "execution_count": 15, "memory_mb": 256}
```

---

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| Kernel not starting | Container resource limits | Increase memory limit |
| Tool execution timeout | Long-running code | Increase timeout or use sandbox |
| Context too large | Too many cells | Uses tiered context automatically |
| Web search not working | API key missing | Check provider API key config |
| SSE events not received | Proxy buffering | Disable nginx buffering |
