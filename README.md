# EASE 2026 Replication Package

This repository contains the experiment code and generated outputs for the EASE 2026 study.

## Repository Contents

- `src/ease2026/`: Python package with hero extraction, outcome computation, and analysis pipelines.
- `artifacts/<dataset_name>/outputs/`: generated CSV tables and plots used in the paper.
- `tests/`: unit tests for core analysis logic.
- `.env.example`: template for SmartSHARK MongoDB connection settings.

## Prerequisites

- Python `>=3.12,<3.13`
- `uv` for environment management
- Access to a SmartSHARK MongoDB dataset (default DB: `smartshark_2_2`)
- Docker (optional, required only for Scott-Knott ESD generation in RQ3 inferential analysis)

## Setup

From this directory:

```powershell
Copy-Item .env.example .env
# Edit .env if needed (SMARTSHARK_MONGO_URI, SMARTSHARK_MONGO_DB)
uv sync
```

Then verify database connectivity:

```powershell
uv run python -m ease2026.cli.run_smoke
```

## Reproducing the Full Pipeline

Run the following commands in order.

1. Generate base hero sets (T1, T2, T3, S1, S2):

```powershell
uv run python -m ease2026.cli.generate_base_heroes --top-fraction 0.20 --coverage-fraction 0.80
```

2. Generate hybrid hero sets (ST1..ST6, TS1..TS6, SH1..SH6):

```powershell
uv run python -m ease2026.cli.generate_hybrid_heroes --top-fraction 0.20 --coverage-fraction 0.80 --hybrid-quantile 0.50
```

3. Compute RQ3 outcomes for both fixer policies:

```powershell
uv run python -m ease2026.cli.compute_rq3_outcomes --fixer assignee
uv run python -m ease2026.cli.compute_rq3_outcomes --fixer commit_author
```

4. Generate final analysis tables (RQ1/RQ2/RQ3) and inferential RQ3 outputs:

```powershell
uv run python -m ease2026.cli.run_all_analysis --inferential-fixer both
```

5. Run threshold robustness sweep:

```powershell
uv run python -m ease2026.cli.run_threshold_sweep
```

6. Generate reviewer robustness artifacts:

```powershell
uv run python -m ease2026.cli.generate_reviewer_robustness
```

7. Generate final paper figures:

```powershell
uv run python -m ease2026.cli.generate_final_figures --fixer assignee
```

## Output Locations

- Hero CSVs: `artifacts/<SMARTSHARK_MONGO_DB>/outputs/csv/heroes/`
- Final analysis tables: `artifacts/<SMARTSHARK_MONGO_DB>/outputs/csv/analysis/final_tables/`
- RQ3 outcomes: `artifacts/<SMARTSHARK_MONGO_DB>/outputs/csv/analysis/rq3_outcomes/`
- RQ3 inferential artifacts: `artifacts/<SMARTSHARK_MONGO_DB>/outputs/csv/analysis/rq3_inferential/`
- Robustness master summary: `artifacts/<SMARTSHARK_MONGO_DB>/outputs/csv/analysis/robustness/threshold_sweep_master.csv`
- Final figures: `artifacts/<SMARTSHARK_MONGO_DB>/outputs/plots/analysis/final_figures/`

## Running Tests

```powershell
uv run pytest
```
