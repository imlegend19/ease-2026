"""Compatibility exports for the legacy ``core.settings`` import path."""

from ease2026.core.settings import BASE_DIR, ENV_FILE_PATH, Settings, settings

__all__ = ["BASE_DIR", "ENV_FILE_PATH", "Settings", "settings"]
