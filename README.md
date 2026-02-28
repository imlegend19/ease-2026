# EASE 2026 (Fresh Workspace)

This is a fresh experiment workspace for EASE-2026.

Current scope:
- Keep SmartSHARK derived-collection materialization scripts.
- Start new RQ implementations from scratch in this directory.

## Data Source

Uses the same SmartSHARK MongoDB instance used by other experiments.

Default expected settings (`.env`):

```env
SMARTSHARK_MONGO_URI=mongodb://smartshark:smartshark@localhost:27117/?authSource=admin
SMARTSHARK_MONGO_DB=smartshark_2_2
```

## Setup

From this directory:

```powershell
uv venv --python 3.12 .venv
uv sync
Copy-Item .env.example .env
```

## Derived Collection Scripts

Run all derived collections:

```powershell
uv run python -m scripts.preprocessing.materialize_derived_collections
```

Run individual steps:

```powershell
uv run python -m scripts.preprocessing.generate_derived_commit_with_project_info
uv run python -m scripts.preprocessing.generate_derived_comments_with_issue_and_project_info
uv run python -m scripts.preprocessing.generate_derived_final_identity
```

## Notes

- This workspace is intentionally minimal.
- Additional pipelines, docs, and analyses should be added incrementally for the new EASE-2026 study.
