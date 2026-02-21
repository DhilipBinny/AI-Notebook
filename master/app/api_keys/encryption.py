"""
Fernet encryption for API keys.
"""

from cryptography.fernet import Fernet
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

_fernet = None


def _get_fernet() -> Fernet:
    """Get or create Fernet instance."""
    global _fernet
    if _fernet is None:
        key = settings.encryption_key
        if not key:
            raise ValueError(
                "ENCRYPTION_KEY not configured. Generate one with: "
                "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def encrypt_key(api_key: str) -> str:
    """Encrypt an API key for storage."""
    f = _get_fernet()
    return f.encrypt(api_key.encode()).decode()


def decrypt_key(encrypted: str) -> str:
    """Decrypt an API key from storage."""
    f = _get_fernet()
    return f.decrypt(encrypted.encode()).decode()


def mask_key(api_key: str) -> str:
    """Create a masked display hint for an API key.
    e.g., 'sk-proj-abc...xyz' → 'sk-...xyz'
    """
    if len(api_key) <= 8:
        return "***"
    return f"{api_key[:3]}...{api_key[-4:]}"
