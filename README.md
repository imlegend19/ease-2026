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

Step 1 (hero CSV generation) and Step 2+ (analysis artifacts) are migrated to a modular layout:

- `core/`: shared configuration, logging, mongo clients, path helpers.
- `identity/`: reusable reverse-identity resolver with pickle cache support.
- `pipelines/common/hero_rules.py`: shared top-20% and 80%-coverage hero rules.
- `pipelines/social/comment_based.py`: migrated pipeline for comment-based social heroes.
- `pipelines/social/issue_based.py`: migrated pipeline for issue-based social heroes.
- `pipelines/technical/commit_based.py`: migrated pipeline for commit-based technical heroes.
- `pipelines/technical/loc_based.py`: migrated pipeline for LOC-based technical heroes.
- `pipelines/technical/file_based.py`: migrated pipeline for file-based technical heroes.
- `pipelines/super/intersection_based.py`: super-hero intersections for all six social/technical combinations.
- `pipelines/socio_technical/median_based.py`: socio-technical heroes (social heroes + technical median filter).
- `pipelines/techno_social/median_based.py`: techno-social heroes (technical heroes + social median filter).
- `pipelines/analysis/hero_catalog.py`: canonical `S*`, `T*`, `TS*`, `ST*`, `SH*` metadata and RQ2 order.
- `pipelines/analysis/hero_membership.py`: project->author membership extraction for all 23 hero types.
- `pipelines/analysis/issue_data.py`: shared issue/event extraction helpers from Mongo.
- `pipelines/analysis/issue_metrics.py`: fixed/reopened issue percentages by hero type and severity.
- `pipelines/analysis/resolution_time.py`: severity-wise assignee averages and hero resolution-time averages.
- `pipelines/analysis/rq2_jaccard.py`: Jaccard matrices + RQ2 plot generation.
- `pipelines/analysis/rq3_rankings.py`: severity-wise rankings + Kendall Tau matrices for RQ3.
- `pipelines/analysis/rq3_sk_esd.py`: Scott-Knott ESD rankings with deterministic fallback when R package is unavailable.
- `scripts/generate_social_comment_heroes.py`: social pipeline CLI.
- `scripts/generate_social_issue_heroes.py`: social issue pipeline CLI.
- `scripts/generate_technical_commit_heroes.py`: technical pipeline CLI.
- `scripts/generate_technical_loc_heroes.py`: technical LOC pipeline CLI.
- `scripts/generate_technical_file_heroes.py`: technical file pipeline CLI.
- `scripts/generate_super_heroes.py`: super-hero intersection pipeline CLI.
- `scripts/generate_socio_technical_heroes.py`: socio-technical hero pipeline CLI.
- `scripts/generate_techno_social_heroes.py`: techno-social hero pipeline CLI.
- `scripts/generate_hero_membership_index.py`: hero-membership index CLI.
- `scripts/generate_issue_outcome_metrics.py`: fixed/reopened issue metrics CLI.
- `scripts/generate_resolution_time_metrics.py`: average resolution-time metrics CLI.
- `scripts/generate_rq2_jaccard_analysis.py`: RQ2 Jaccard matrices/plots CLI.
- `scripts/generate_rq3_rankings.py`: RQ3 ranking and Kendall Tau CLI.
- `scripts/generate_rq3_sk_esd.py`: RQ3 Scott-Knott ESD CLI.
- `scripts/generate_analysis_artifacts.py`: run all migrated analysis pipelines.

Run the migrated pipelines:

```powershell
cd experiments/ease-2026
.venv\Scripts\python.exe -m scripts.generate_social_comment_heroes
.venv\Scripts\python.exe -m scripts.generate_social_issue_heroes
.venv\Scripts\python.exe -m scripts.generate_technical_commit_heroes
.venv\Scripts\python.exe -m scripts.generate_technical_loc_heroes
.venv\Scripts\python.exe -m scripts.generate_technical_file_heroes
.venv\Scripts\python.exe -m scripts.generate_super_heroes
.venv\Scripts\python.exe -m scripts.generate_socio_technical_heroes
.venv\Scripts\python.exe -m scripts.generate_techno_social_heroes
.venv\Scripts\python.exe -m scripts.generate_analysis_artifacts
```

Artifacts are written under `artifacts/`:

- `artifacts/cache/identity/` for identity cache.
- `artifacts/interim/social/comment_based/`, `artifacts/interim/social/issue_based/`,
  and `artifacts/interim/technical/commit_based/`, `artifacts/interim/technical/loc_based/`,
  `artifacts/interim/technical/file_based/`, `artifacts/interim/super/`,
  `artifacts/interim/socio_technical/`, `artifacts/interim/techno_social/`,
  `artifacts/interim/analysis/` for intermediate pickles.
- `artifacts/outputs/csv/social/`, `artifacts/outputs/csv/technical/`,
  `artifacts/outputs/csv/super/`, `artifacts/outputs/csv/socio_technical/`,
  `artifacts/outputs/csv/techno_social/`, `artifacts/outputs/csv/analysis/` for final CSV output.
- `artifacts/outputs/plots/rq2/` for generated RQ2 plot files.

## Artifact Versioning Policy

- `artifacts/outputs/csv/**` is committed to git for reproducibility snapshots.
- `artifacts/cache/**`, `artifacts/interim/**`, and `artifacts/outputs/plots/**` are ignored
  because they are environment-dependent or large/intermediate byproducts.
