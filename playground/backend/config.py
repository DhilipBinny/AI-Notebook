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

# === Ollama Configuration (default - no API key needed) ===
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://192.168.0.136:11434/v1")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3-coder:30b")

# === Gemini Configuration ===
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# === OpenAI Configuration ===
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")

# === Anthropic Configuration ===
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

# === OpenRouter Configuration (OpenAI-compatible API) ===
# Set USE_OPENROUTER=true to route OpenAI requests through OpenRouter
USE_OPENROUTER = os.environ.get("USE_OPENROUTER", "false").lower() == "true"
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_OPENAI_URL = os.environ.get("OPENROUTER_OPENAI_URL", "https://openrouter.ai/api/v1")
OPENROUTER_OPENAI_MODEL = os.environ.get("OPENROUTER_OPENAI_MODEL", "openai/gpt-4o")
OPENROUTER_MAX_TOKENS = int(os.environ.get("OPENROUTER_MAX_TOKENS", "4000"))

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
    """Auto-detect default provider - Ollama as container default"""
    # Note: Container defaults to Ollama, but UI sends actual selection on each call
    return "ollama"

# Read from environment or use default
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", _get_default_provider())

# # === Legacy support (backwards compatibility) ===
# API_KEY = GEMINI_API_KEY  # Keep for backward compatibility
# MODEL = GEMINI_MODEL


def get_provider_info():
    """Get information about the current provider configuration"""
    return {
        "provider": LLM_PROVIDER,
        "auto_function_calling": AUTO_FUNCTION_CALLING,
        "tool_execution_mode": TOOL_EXECUTION_MODE,
        "context_format": CONTEXT_FORMAT,
        "ollama": {
            "configured": True,  # Always available (no key needed)
            "model": OLLAMA_MODEL,
            "url": OLLAMA_URL
        },
        "gemini": {
            "configured": bool(GEMINI_API_KEY),
            "model": GEMINI_MODEL
        },
        "openai": {
            "configured": bool(OPENAI_API_KEY) or (USE_OPENROUTER and bool(OPENROUTER_API_KEY)),
            "model": OPENROUTER_OPENAI_MODEL if USE_OPENROUTER else OPENAI_MODEL,
            "via_openrouter": USE_OPENROUTER
        },
        "anthropic": {
            "configured": bool(ANTHROPIC_API_KEY),
            "model": ANTHROPIC_MODEL
        }
    }
