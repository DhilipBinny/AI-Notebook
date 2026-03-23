"""
Input sanitization and prompt injection detection.

Cleans user input before sending to LLMs and detects common
prompt injection / jailbreak patterns.
"""

import re
import unicodedata
from typing import Tuple


MAX_INPUT_LENGTH = 50_000

INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|above|prior)\s+instructions", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+", re.IGNORECASE),
    re.compile(r"new\s+instructions?\s*:", re.IGNORECASE),
    re.compile(r"system\s*:\s*", re.IGNORECASE),
    re.compile(r"<\|?(system|im_start|endoftext|assistant)", re.IGNORECASE),
    re.compile(r"reveal\s+(your\s+)?(system\s+)?prompt", re.IGNORECASE),
    re.compile(r"pretend\s+(you\s+are|to\s+be)\s+", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
    re.compile(r"DAN\s+mode", re.IGNORECASE),
    re.compile(r"\bdo\s+anything\s+now\b", re.IGNORECASE),
    re.compile(r"bypass\s+(your\s+)?(safety|filter|restriction)", re.IGNORECASE),
]


def sanitize_input(text: str, max_length: int = MAX_INPUT_LENGTH) -> str:
    """
    Sanitize user input text.

    - Strips null bytes and control characters (except newline/tab)
    - Normalizes unicode to NFC form
    - Enforces maximum length
    """
    if not text:
        return ""

    # Strip null bytes
    text = text.replace("\x00", "")

    # Remove control characters except \n, \r, \t
    text = "".join(c for c in text if ord(c) >= 32 or c in "\n\r\t")

    # Normalize unicode
    text = unicodedata.normalize("NFC", text)

    text = text.strip()

    # Enforce max length
    if len(text) > max_length:
        text = text[:max_length]

    return text


def detect_prompt_injection(text: str) -> Tuple[bool, str]:
    """
    Detect likely prompt injection attempts.

    Returns:
        (detected, matched_pattern) — True if a pattern matched.

    Note: This is a heuristic — false positives are possible.
    Log and flag but don't necessarily block.
    """
    if not text:
        return False, ""

    for pattern in INJECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            return True, match.group(0)

    return False, ""
