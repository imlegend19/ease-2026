"""Settings for EASE 2026 scripts loaded from environment variables."""

import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _discover_base_dir() -> Path:
    current_file = Path(__file__).resolve()
    for parent in current_file.parents:
        if (parent / "pyproject.toml").exists():
            return parent

    parents = current_file.parents
    fallback_index = 3 if len(parents) > 3 else len(parents) - 1
    return parents[fallback_index]


BASE_DIR = _discover_base_dir()
ENV_FILE_PATH = BASE_DIR / ".env"

if ENV_FILE_PATH.exists():
    load_dotenv(ENV_FILE_PATH, override=False)


def _sanitize_dataset_name(raw_name: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", raw_name.strip())
    normalized = normalized.strip("._-")
    return normalized or "smartshark"


DEFAULT_SMARTSHARK_DB = os.getenv("SMARTSHARK_MONGO_DB", "smartshark")
DEFAULT_DATASET_NAME = _sanitize_dataset_name(DEFAULT_SMARTSHARK_DB)


@dataclass(frozen=True, slots=True)
class Settings:
    smartshark_mongo_uri: str = os.getenv(
        "SMARTSHARK_MONGO_URI",
        "mongodb://smartshark:smartshark@localhost:27117/?authSource=admin",
    )
    smartshark_mongo_db: str = DEFAULT_SMARTSHARK_DB
    dataset_name: str = DEFAULT_DATASET_NAME

    experiment_root: Path = BASE_DIR
    artifacts_root_dir: Path = BASE_DIR / "artifacts"
    artifacts_dir: Path = artifacts_root_dir / dataset_name
    cache_dir: Path = artifacts_dir / "cache"
    interim_dir: Path = artifacts_dir / "interim"
    outputs_dir: Path = artifacts_dir / "outputs"
    outputs_csv_dir: Path = outputs_dir / "csv"
    outputs_plots_dir: Path = outputs_dir / "plots"

    identity_cache_path: Path = cache_dir / "identity" / "reverse_identity.pkl"


settings = Settings()
