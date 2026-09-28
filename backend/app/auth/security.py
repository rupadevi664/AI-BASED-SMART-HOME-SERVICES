"""Security helpers re-exported for the auth package.

The single source of truth is app.core.security; this module keeps the
documented `app.auth.security` import path working for later phases.
"""
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

__all__ = ["create_access_token", "decode_access_token", "hash_password", "verify_password"]
