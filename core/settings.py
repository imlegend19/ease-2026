"""Settings for EASE 2026 scripts loaded from environment variables."""


import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
ENV_FILE_PATH = BASE_DIR / ".env"

if ENV_FILE_PATH.exists():
    load_dotenv(ENV_FILE_PATH, override=False)


@dataclass(frozen=True, slots=True)
class Settings:
    smartshark_mongo_uri: str = os.getenv(
        "SMARTSHARK_MONGO_URI",
        "mongodb://smartshark:smartshark@localhost:27117/?authSource=admin",
    )
    smartshark_mongo_db: str = os.getenv("SMARTSHARK_MONGO_DB", "smartshark")

    artifacts_dir: Path = BASE_DIR / "artifacts"
    cache_dir: Path = artifacts_dir / "cache"
    interim_dir: Path = artifacts_dir / "interim"
    outputs_dir: Path = artifacts_dir / "outputs"
    outputs_csv_dir: Path = outputs_dir / "csv"
    outputs_plots_dir: Path = outputs_dir / "plots"

    identity_cache_path: Path = cache_dir / "identity" / "reverse_identity.pkl"


settings = Settings()

