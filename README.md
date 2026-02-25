# EASE 2026 Experiment Workspace

This experiment uses the shared SmartSHARK MongoDB service in
`datasets/smartshark`. Mongo access in Python is through `pymongo`.

## 1. Start shared SmartSHARK MongoDB

From workspace root:

```powershell
cd datasets/smartshark
docker compose up -d mongo
docker compose --profile restore run --rm mongo-restore
```

## 2. Configure this experiment

From `experiments/ease-2026`:

```powershell
Copy-Item .env.example .env
```

Defaults:

- `SMARTSHARK_MONGO_URI=mongodb://smartshark:smartshark@localhost:27117/?authSource=admin`
- `SMARTSHARK_MONGO_DB=smartshark`

## 3. Create local `uv` environment (Python 3.12)

From `experiments/ease-2026`:

```powershell
# Install uv (one-time) if needed
irm https://astral.sh/uv/install.ps1 | iex

# Create local virtual environment with Python 3.12
uv venv --python 3.12 .venv
```

## 4. Install experiment dependencies (latest)

From `experiments/ease-2026`:

```powershell
uv pip install --python .venv\Scripts\python.exe --upgrade `
  pandas numpy scipy matplotlib seaborn pymongo rbo rpy2 `
  python-dotenv structlog `
  networkx upsetplot scikit-learn
```

## 5. Verify the environment

```powershell
.venv\Scripts\python.exe --version
uv pip list --python .venv\Scripts\python.exe
```

## Notes

- Dependency set above was derived from `experiments/saner-2026` scripts and requirements.
- `experiments/saner-2026/rq3_scott-knot.py` imports `from sk import Rx`; this helper module is not present in `saner-2026` as a pip dependency.

## Migration Progress

Step 1 has been migrated to a modular layout:

- `core/`: shared configuration, logging, mongo clients, path helpers.
- `identity/`: reusable reverse-identity resolver with pickle cache support.
- `pipelines/common/hero_rules.py`: shared top-20% and 80%-coverage hero rules.
- `pipelines/social/comment_based.py`: migrated pipeline for comment-based social heroes.
- `pipelines/social/issue_based.py`: migrated pipeline for issue-based social heroes.
- `pipelines/technical/commit_based.py`: migrated pipeline for commit-based technical heroes.
- `pipelines/technical/loc_based.py`: migrated pipeline for LOC-based technical heroes.
- `pipelines/technical/file_based.py`: migrated pipeline for file-based technical heroes.
- `scripts/generate_social_comment_heroes.py`: social pipeline CLI.
- `scripts/generate_social_issue_heroes.py`: social issue pipeline CLI.
- `scripts/generate_technical_commit_heroes.py`: technical pipeline CLI.
- `scripts/generate_technical_loc_heroes.py`: technical LOC pipeline CLI.
- `scripts/generate_technical_file_heroes.py`: technical file pipeline CLI.

Run the migrated pipelines:

```powershell
cd experiments/ease-2026
.venv\Scripts\python.exe -m scripts.generate_social_comment_heroes
.venv\Scripts\python.exe -m scripts.generate_social_issue_heroes
.venv\Scripts\python.exe -m scripts.generate_technical_commit_heroes
.venv\Scripts\python.exe -m scripts.generate_technical_loc_heroes
.venv\Scripts\python.exe -m scripts.generate_technical_file_heroes
```

Artifacts are written under `artifacts/`:

- `artifacts/cache/identity/` for identity cache.
- `artifacts/interim/social/comment_based/`, `artifacts/interim/social/issue_based/`,
  and `artifacts/interim/technical/commit_based/`, `artifacts/interim/technical/loc_based/`,
  `artifacts/interim/technical/file_based/` for intermediate pickles.
- `artifacts/outputs/csv/social/` and `artifacts/outputs/csv/technical/` for final CSV output.
