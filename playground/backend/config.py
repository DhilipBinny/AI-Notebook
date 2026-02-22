# LLM Configuration - Supports multiple providers
#
# In Docker: All configuration is passed via environment variables from master-api.
# Locally: Load from .env file for development convenience.
import os
from pathlib import Path
import sys
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env file if it exists (for local development)
load_dotenv(Path(__file__).parent / ".env")

# === Master API Configuration ===
# URL for the master API (for LLM tools to fetch notebook data)
MASTER_API_URL = os.environ.get("MASTER_API_URL", "http://master-api:8000/api")
INTERNAL_SECRET = os.environ.get("INTERNAL_SECRET", "dev-internal-secret")

# === Workspace Configuration ===
# Root path inside the container where master restores project files
WORKSPACE_PATH = "/workspace"

# === LLM Provider Configuration ===
# SECURITY: API keys are NEVER stored in environment variables.
# Users can run os.environ in notebooks, so all LLM credentials are injected
# exclusively via per-request HTTP headers by the master API (see chat/routes.py
# _build_proxy_headers and middleware/security.py extract_key_overrides).
#
# The defaults below are used ONLY when no header override is provided (e.g. local dev).

# OpenAI-Compatible (Ollama, OpenRouter, vLLM, etc.)
OPENAI_COMPATIBLE_BASE_URL = os.environ.get("OPENAI_COMPATIBLE_BASE_URL", "http://localhost:11434/v1")
OPENAI_COMPATIBLE_API_KEY = os.environ.get("OPENAI_COMPATIBLE_API_KEY", "")
OPENAI_COMPATIBLE_MODEL = os.environ.get("OPENAI_COMPATIBLE_MODEL", "qwen3-coder:30b")

# Gemini — key comes via per-request headers in production
GEMINI_API_KEY = None
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# OpenAI — key comes via per-request headers in production
OPENAI_API_KEY = None
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")

# Anthropic — key comes via per-request headers in production
ANTHROPIC_API_KEY = None
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

# === Function Calling Behavior ===
# Tool execution mode:
#   "auto" - LLM automatically executes tools without user approval
#   "manual" - LLM returns pending tool calls for user to approve/reject
#   "ai_decide" - AI validator decides which tools need approval
# Note: Container default is "ai_decide", but UI sends actual selection on each call
TOOL_EXECUTION_MODE = os.environ.get("TOOL_EXECUTION_MODE", "ai_decide")

# Maximum iterations for auto tool calling loops (Chat Panel and AI Cell)
# Prevents infinite loops when LLM keeps calling tools
MAX_TOOL_ITERATIONS = int(os.environ.get("MAX_TOOL_ITERATIONS", "10"))

# Legacy support - AUTO_FUNCTION_CALLING maps to mode
AUTO_FUNCTION_CALLING = os.environ.get("AUTO_FUNCTION_CALLING", "false").lower() == "true"
if AUTO_FUNCTION_CALLING:
    TOOL_EXECUTION_MODE = "auto"

# === Web Search ===
# Enable native web search for LLM providers (Gemini, OpenAI, Anthropic)
# Each provider uses its own search: Google Search, Bing, Brave respectively
ENABLE_WEB_SEARCH = os.environ.get("ENABLE_WEB_SEARCH", "true").lower() == "true"

# === Context Format ===
# Format for LLM context: "xml" or "plain"
# XML is recommended for Claude (improves accuracy by up to 40%)
# Note: Container default is "xml", but UI can override on each call
CONTEXT_FORMAT = os.environ.get("CONTEXT_FORMAT", "xml")

# === AI Cell Streaming ===
# Enable real-time SSE progress events for AI Cell execution
# When enabled: sends thinking, tool_call, tool_result events during execution
# When disabled: only sends final 'done' event with complete result
# Both modes use SSE (unified interface), just different verbosity
AI_CELL_STREAMING_ENABLED = os.environ.get("AI_CELL_STREAMING_ENABLED", "true").lower() == "true"

# === Provider Selection ===
# Auto-detect default based on availability
# User can switch via UI dropdown at runtime
def _get_default_provider():
    """Auto-detect default provider - OpenAI-compatible as container default"""
    return "openai_compatible"

# Read from environment or use default
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", _get_default_provider())

# # === Legacy support (backwards compatibility) ===
# API_KEY = GEMINI_API_KEY  # Keep for backward compatibility
# MODEL = GEMINI_MODEL


def get_provider_info():
    """Get information about the current provider configuration.

    Note: gemini/openai/anthropic keys are None in production (injected per-request
    via headers). 'configured' here reflects local dev env only.
    """
    return {
        "provider": LLM_PROVIDER,
        "auto_function_calling": AUTO_FUNCTION_CALLING,
        "tool_execution_mode": TOOL_EXECUTION_MODE,
        "context_format": CONTEXT_FORMAT,
        "openai_compatible": {
            "configured": True,  # Always available (base_url can default to localhost)
            "model": OPENAI_COMPATIBLE_MODEL,
            "url": OPENAI_COMPATIBLE_BASE_URL
        },
        "gemini": {
            "configured": bool(GEMINI_API_KEY),
            "model": GEMINI_MODEL
        },
        "openai": {
            "configured": bool(OPENAI_API_KEY),
            "model": OPENAI_MODEL,
        },
        "anthropic": {
            "configured": bool(ANTHROPIC_API_KEY),
            "model": ANTHROPIC_MODEL
        }
    }
