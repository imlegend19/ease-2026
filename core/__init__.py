"""Compatibility exports for the legacy ``core`` package path.

Prefer importing from ``ease2026.core`` in new code.
"""

from ease2026.core.settings import Settings, settings

__all__ = ["Settings", "settings"]
