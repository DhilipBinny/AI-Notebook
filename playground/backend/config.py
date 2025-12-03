# LLM Configuration - Supports multiple providers
import os
from pathlib import Path
import sys
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables from backend folder
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
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-1-20250805")

# === Function Calling Behavior ===
# Tool execution mode:
#   "auto" - LLM automatically executes tools without user approval
#   "manual" - LLM returns pending tool calls for user to approve/reject
#   "ai_decide" - AI validator decides which tools need approval
TOOL_EXECUTION_MODE = os.environ.get("TOOL_EXECUTION_MODE", "auto")

# Legacy support - AUTO_FUNCTION_CALLING maps to mode
AUTO_FUNCTION_CALLING = os.environ.get("AUTO_FUNCTION_CALLING", "false").lower() == "true"
if AUTO_FUNCTION_CALLING:
    TOOL_EXECUTION_MODE = "auto"

# === Web Search ===
# Enable native web search for LLM providers (Gemini, OpenAI, Anthropic)
# Each provider uses its own search: Google Search, Bing, Brave respectively
ENABLE_WEB_SEARCH = os.environ.get("ENABLE_WEB_SEARCH", "true").lower() == "true"

# === Provider Selection ===
# Auto-detect default based on availability
# User can switch via UI dropdown at runtime
def _get_default_provider():
    """Auto-detect default provider - Gemini as default"""
    return "gemini"

LLM_PROVIDER = _get_default_provider()

# # === Legacy support (backwards compatibility) ===
# API_KEY = GEMINI_API_KEY  # Keep for backward compatibility
# MODEL = GEMINI_MODEL


def get_provider_info():
    """Get information about the current provider configuration"""
    return {
        "provider": LLM_PROVIDER,
        "auto_function_calling": AUTO_FUNCTION_CALLING,
        "tool_execution_mode": TOOL_EXECUTION_MODE,
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
            "configured": bool(OPENAI_API_KEY),
            "model": OPENAI_MODEL
        },
        "anthropic": {
            "configured": bool(ANTHROPIC_API_KEY),
            "model": ANTHROPIC_MODEL
        }
    }
