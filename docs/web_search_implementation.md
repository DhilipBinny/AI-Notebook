# Web Search Implementation

How web search works across LLM providers in this project.

Last updated: 2026-03-07

---

## Overview

There are two separate web search mechanisms:

1. **Native provider search** - Built-in search tools from Anthropic/OpenAI/Gemini
2. **`web_fetch` tool** - Our custom tool that fetches a specific URL

These are independent. Native search finds information. `web_fetch` downloads a specific URL the LLM asks for.

---

## Native Provider Search

### Strategy

| Provider | Strategy | How |
|----------|----------|-----|
| **Anthropic** | Always included | Web search tool added to every request. Claude decides when to call it. |
| **OpenAI** | Always included | Web search tool added to every request. GPT decides when to call it. |
| **Gemini** | Two-phase with pre-filter | Weighted scoring decides IF search is needed. If yes, separate API call with Google Search grounding, results injected as context. |
| **Ollama** | None | Local models, no web search. |

### Why Anthropic/OpenAI always include search

These providers handle web search as a native tool type. The model receives the tool schema and decides whether to call it based on the user's question. Pre-filtering with regex:
- Adds false negatives (user can't search when they should)
- Is redundant (model already makes this decision)
- Costs nothing extra if not called (~50 tokens for the tool definition)

### Why Gemini uses pre-filtering

Gemini's Google Search grounding requires a **separate API call** before the main completion. This means:
- Extra latency (two round trips)
- Extra cost (two API calls)
- Search results must be injected as text context

So we use weighted keyword scoring to avoid unnecessary search calls.

---

## Weighted Scoring (Gemini only)

Defined in `playground/backend/llm_clients/base.py`.

| Category | Score | Examples |
|----------|-------|---------|
| Explicit commands | +100 | "google", "search for", "look up", "web search" |
| Dynamic/time-sensitive | +15 | "latest", "current", "today", "news", "weather", "stock price", year numbers |
| Informational/docs | +5 | "who is", "what is", "docs for", "api reference", "official docs" |
| Local context | -20 | "my code", "this cell", "my dataframe", "fix this", "debug this" |
| Coding intent | -10 | "def ", "class ", "import ", "write a function", "generate code" |

**Threshold**: Score >= 10 triggers search.

**Examples**:
- "weather in Tokyo" = +15 dynamic -> SEARCH
- "write code for stock analysis" = +15 dynamic - 10 coding = 5 -> NO SEARCH
- "google pandas documentation" = +100 explicit -> SEARCH
- "fix this error in my code" = -20 local -> NO SEARCH

---

## Code Locations

### Core
- `base.py:_needs_web_search()` - Weighted scoring (used by Gemini)
- `base.py:_get_web_search_tool()` - Abstract method, returns provider-specific tool
- `base.py:ai_cell_execute()` - Always includes web search tool for AI Cell

### Per Provider

**Anthropic** (`anthropic.py`):
- `_get_tools_for_request()` - Always appends `web_search_20250305` tool
- `_get_web_search_tool()` - Returns `{"type": "web_search_20250305", "name": "web_search", "max_uses": N}`
- Adapter: `anthropic_adapter.py:get_web_search_tool(max_uses)`

**OpenAI** (`openai.py`):
- `_get_tools_for_request()` - Always appends `web_search_preview` tool
- `_get_web_search_tool()` - Returns `{"type": "web_search_preview", "search_context_size": "medium"}`
- Adapter: `openai_adapter.py:get_web_search_tool()`

**Gemini** (`gemini.py`):
- Chat Panel: `_needs_web_search()` -> `_gemini_do_google_search()` -> inject results
- AI Cell: `_get_web_search_tool()` returns `types.Tool(google_search=GoogleSearch())` for grounding
- `_gemini_do_google_search()` - Separate API call with search-only config, extracts grounding metadata and sources
- Adapter: `gemini_adapter.py:get_web_search_tool()`

**Ollama** (`ollama.py`):
- `enable_web_search = False` on init
- `_get_web_search_tool()` returns `None` (via adapter)

---

## `web_fetch` Tool (separate from native search)

Custom tool in `playground/backend/llm_tools/tool_web_fetch.py`.

- Fetches a specific URL provided by the LLM
- Converts HTML to markdown, parses JSON/CSV
- Can save fetched content to workspace
- Available in: Chat Panel (TOOL_FUNCTIONS), AI Cell Power mode (ALL_AI_CELL_TOOLS)
- NOT available in: AI Cell Crisp/Standard modes

This is a function-calling tool, not a native search. The LLM explicitly calls `web_fetch(url="https://...")` when it needs content from a known URL.

---

## Configuration

- `ENABLE_WEB_SEARCH` in `backend/config.py` - Global toggle (env var)
- Passed to each client constructor as `enable_web_search` parameter
- Set via `playground/backend/llm_clients/client.py` when creating clients

---

## Flow Diagrams

### Anthropic/OpenAI (Chat Panel)
```
User message
  -> _get_tools_for_request()
     -> Always includes web search tool
  -> Send to API with tools
  -> Model decides to call web_search or not
  -> Response (may include search results inline)
```

### Gemini (Chat Panel)
```
User message
  -> _needs_web_search(user_prompt)  [weighted scoring]
     -> If NO: skip to completion
     -> If YES:
        -> _gemini_do_google_search(query)  [separate API call]
        -> Get search results + grounding sources
  -> Send to API with search context injected + function tools
  -> Response
```

### AI Cell (all providers)
```
User message
  -> ai_cell_execute()  [base class]
  -> _get_web_search_tool()  [provider-specific]
     -> Anthropic: web_search tool type
     -> OpenAI: web_search_preview tool type
     -> Gemini: GoogleSearch grounding tool
     -> Ollama: None
  -> Always included in tool list (model decides usage)
  -> Tool execution loop with cancellation support
  -> Response
```
