"""
Output filtering and secret redaction.

Scans LLM output for accidentally leaked secrets (API keys, tokens,
passwords, database URLs) and redacts them before sending to the user.
"""

import re
from typing import List, Tuple


REDACT_PATTERNS: List[Tuple[re.Pattern, str]] = [
    # Anthropic API keys
    (re.compile(r"sk-ant-api[A-Za-z0-9_-]{20,}"), "[REDACTED_ANTHROPIC_KEY]"),
    # Anthropic OAuth tokens
    (re.compile(r"sk-ant-oat[A-Za-z0-9_-]{20,}"), "[REDACTED_ANTHROPIC_TOKEN]"),
    # OpenAI project keys
    (re.compile(r"sk-proj-[A-Za-z0-9_-]{20,}"), "[REDACTED_OPENAI_KEY]"),
    # Generic sk- keys (OpenAI legacy, etc.)
    (re.compile(r"sk-[A-Za-z0-9]{32,}"), "[REDACTED_API_KEY]"),
    # Google/Gemini API keys (AIza...)
    (re.compile(r"AIza[A-Za-z0-9_-]{30,}"), "[REDACTED_GOOGLE_KEY]"),
    # Bearer tokens
    (re.compile(r"Bearer\s+[A-Za-z0-9._-]{20,}"), "Bearer [REDACTED]"),
    # JWTs (three base64 segments)
    (re.compile(r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"), "[REDACTED_JWT]"),
    # Database URLs
    (re.compile(r"mysql://[^\s'\"]+"), "[REDACTED_DB_URL]"),
    (re.compile(r"postgresql://[^\s'\"]+"), "[REDACTED_DB_URL]"),
    (re.compile(r"mongodb://[^\s'\"]+"), "[REDACTED_DB_URL]"),
    # Password/secret assignments (key=value or key: value patterns)
    (re.compile(r"(?i)(password|passwd|secret|token|api_key|apikey)\s*[=:]\s*['\"]?[^\s'\"]{8,}"), "[REDACTED_SECRET]"),
    # Fernet keys (base64, 44 chars)
    (re.compile(r"[A-Za-z0-9_-]{43}="), None),  # Skip — too many false positives
]

# Only apply patterns that have a replacement string
_ACTIVE_PATTERNS = [(p, r) for p, r in REDACT_PATTERNS if r is not None]


def redact_secrets(text: str) -> str:
    """
    Redact potential secrets from text.

    Scans for common API key, token, and credential patterns
    and replaces them with [REDACTED_*] placeholders.
    """
    if not text:
        return text

    for pattern, replacement in _ACTIVE_PATTERNS:
        text = pattern.sub(replacement, text)

    return text
