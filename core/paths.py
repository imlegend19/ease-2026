"""Path helpers for generated artifacts."""

from __future__ import annotations

from pathlib import Path

from core.settings import settings


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_artifact_directories() -> None:
    ensure_directory(settings.cache_dir)
    ensure_directory(settings.interim_dir)
    ensure_directory(settings.outputs_csv_dir)
    ensure_directory(settings.outputs_plots_dir)
