# EASE 2026 Developer Guide

This project analyzes SmartSHARK data to identify different kinds of "hero developers"
and compare their bug-fixing performance.

In simple terms, the code does three big things:

1. Finds hero developers from technical and social contribution metrics.
2. Builds combined hero categories (socio-technical, techno-social, super).
3. Runs analysis for prevalence (RQ1), overlap (RQ2), and bug-fixing performance (RQ3).

The definitions and goals follow the paper in `papers/ease-2026/main.tex`.

## What The Pipeline Produces

- Social hero CSVs (2 types): `S1`, `S2`
- Technical hero CSVs (3 types): `T1`, `T2`, `T3`
- Combined hero CSVs (18 types): `ST1..ST6`, `TS1..TS6`, `SH1..SH6`
- Analysis outputs for:
  - RQ2 Jaccard overlap matrices and plots
  - RQ3 fixed/reopened bug metrics, rankings, and Kendall Tau correlations

Total hero categories: `23`.

## Project Structure (Complete Map)

```text
experiments/ease-2026/
|-- .env.example                 # Mongo connection template
|-- pyproject.toml               # Python project + dependencies
|-- uv.lock                      # locked dependency versions
|-- README.md                    # this file
|
|-- core/                        # shared infrastructure
|   |-- settings.py              # env loading (.env), paths, db name
|   |-- mongo.py                 # synced MongoDB client helpers
|   |-- mongo_async.py           # async Mongo client helpers
|   |-- constants.py             # collection names and thresholds
|   |-- logging.py               # structlog setup
|   `-- paths.py                 # artifact directory helpers
|
|-- identity/
|   `-- reverse_identity.py      # maps person -> merged identity (cached pickle)
|
|-- pipelines/
|   |-- preprocessing/
|   |   `-- derived_collections.py    # builds derived Mongo collections
|   |-- common/
|   |   `-- hero_rules.py             # top-20% + 80%-coverage hero logic
|   |-- social/
|   |   |-- comment_based.py          # S1
|   |   `-- issue_based.py            # S2
|   |-- technical/
|   |   |-- commit_based.py           # T1
|   |   |-- file_based.py             # T2
|   |   |-- loc_based.py              # T3
|   |   `-- shared.py                 # shared commit->(project,author) index
|   |-- super/
|   |   `-- intersection_based.py     # SH1..SH6 (strict intersections)
|   |-- socio_technical/
|   |   `-- median_based.py           # ST1..ST6 (social hero + tech median)
|   |-- techno_social/
|   |   `-- median_based.py           # TS1..TS6 (technical hero + social median)
|   `-- analysis/
|       |-- hero_catalog.py           # canonical hero-code metadata/order
|       |-- hero_membership.py        # project->hero-author index
|       |-- issue_data.py             # issue/event extraction from Mongo
|       |-- issue_metrics.py          # fixed/reopened percentages
|       |-- resolution_time.py        # resolution-time metrics
|       |-- rq2_jaccard.py            # RQ2 similarity matrices/plots
|       |-- rq3_rankings.py           # RQ3 rankings + Kendall Tau
|       `-- rq3_sk_esd.py             # optional Scott-Knott ESD ranking
|
|-- scripts/                     # runnable CLI entry points (grouped)
|   |-- preprocessing/           # derived collection materialization scripts
|   |-- heroes/                  # social/technical/super hero generation scripts
|   `-- analysis/                # RQ2/RQ3 and metrics scripts
|
`-- artifacts/                   # generated runtime outputs
    |-- cache/                   # identity cache pickle
    |-- interim/                 # intermediate pickles used by later steps
    `-- outputs/
        |-- csv/                 # final CSV outputs
        `-- plots/               # generated figures (RQ2)
```

## Data Requirements (MongoDB)

The code expects SmartSHARK data in one DB (your case: `smartshark_2_2`).

Base collections used:
- `project`, `vcs_system`, `commit`, `file_action`
- `issue_system`, `issue`, `issue_comment`, `event`
- `people` (for identity grouping when available)

Derived collections expected:
- `commit_with_project_info`
- `comments_with_issue_and_project_info`
- `final_identity`

If those three derived collections are already restored, you can skip regeneration.

## Setup

From workspace root, ensure Mongo is running:

```powershell
cd datasets/smartshark
docker compose up -d mongo
```

From `experiments/ease-2026`, set environment:

```powershell
Copy-Item .env.example .env
```

Then edit `.env` and set:

```env
SMARTSHARK_MONGO_URI=mongodb://smartshark:smartshark@localhost:27117/?authSource=admin
SMARTSHARK_MONGO_DB=smartshark_2_2
```

Create environment and install dependencies:

```powershell
uv venv --python 3.12 .venv
uv sync
```

## Recommended Execution Order

Run from `experiments/ease-2026`.

Option A (recommended): one command to run all hero generation once.

```powershell
python -m scripts.heroes.generate_all_heroes --refresh-identity-cache
python -m scripts.analysis.generate_analysis_artifacts
```

Option B: run each hero script separately.

```powershell
python -m scripts.heroes.generate_social_comment_heroes --refresh-identity-cache
python -m scripts.heroes.generate_social_issue_heroes
python -m scripts.heroes.generate_technical_commit_heroes
python -m scripts.heroes.generate_technical_loc_heroes
python -m scripts.heroes.generate_technical_file_heroes
python -m scripts.heroes.generate_super_heroes
python -m scripts.heroes.generate_socio_technical_heroes
python -m scripts.heroes.generate_techno_social_heroes
python -m scripts.analysis.generate_analysis_artifacts
```

Note:
- `generate_super_heroes`, `generate_socio_technical_heroes`, and `generate_techno_social_heroes`
  now use existing prerequisite artifacts by default.
- They first check that prerequisite artifact files exist; if not, they stop and print
  the exact prerequisite script commands you should run.
- If you want those scripts to re-run prerequisites inside the same command, pass
  `--include-prerequisites`.

## If Derived Collections Are Missing

Build all derived collections in one command:

```powershell
python -m scripts.preprocessing.materialize_derived_collections
```

Or run them one by one:

```powershell
python -m scripts.preprocessing.generate_derived_commit_with_project_info
python -m scripts.preprocessing.generate_derived_comments_with_issue_and_project_info
python -m scripts.preprocessing.generate_derived_final_identity
```

## Script Cheat Sheet

Data preparation:
- `scripts.preprocessing.materialize_derived_collections`
- `scripts.preprocessing.generate_derived_commit_with_project_info`
- `scripts.preprocessing.generate_derived_comments_with_issue_and_project_info`
- `scripts.preprocessing.generate_derived_final_identity`

Hero generation:
- `scripts.heroes.generate_all_heroes` (all hero categories end-to-end)
- `scripts.heroes.generate_social_comment_heroes` (`S1`)
- `scripts.heroes.generate_social_issue_heroes` (`S2`)
- `scripts.heroes.generate_technical_commit_heroes` (`T1`)
- `scripts.heroes.generate_technical_file_heroes` (`T2`)
- `scripts.heroes.generate_technical_loc_heroes` (`T3`)
- `scripts.heroes.generate_super_heroes` (`SH1..SH6`)
- `scripts.heroes.generate_socio_technical_heroes` (`ST1..ST6`)
- `scripts.heroes.generate_techno_social_heroes` (`TS1..TS6`)

Analysis:
- `scripts.analysis.generate_hero_membership_index`
- `scripts.analysis.generate_issue_outcome_metrics`
- `scripts.analysis.generate_resolution_time_metrics`
- `scripts.analysis.generate_rq2_jaccard_analysis`
- `scripts.analysis.generate_rq3_rankings`
- `scripts.analysis.generate_rq3_sk_esd`
- `scripts.analysis.generate_analysis_artifacts` (all analysis steps in one run)

## Outputs

Main output locations:
- `artifacts/outputs/csv/social/`
- `artifacts/outputs/csv/technical/`
- `artifacts/outputs/csv/super/`
- `artifacts/outputs/csv/socio_technical/`
- `artifacts/outputs/csv/techno_social/`
- `artifacts/outputs/csv/analysis/`
- `artifacts/outputs/plots/rq2/`

Intermediates and cache:
- `artifacts/interim/**`
- `artifacts/cache/identity/reverse_identity.pkl`

## Notes

- `generate_analysis_artifacts` assumes hero CSVs exist; it does not generate them.
- RQ3 SK-ESD uses `rpy2` when available and falls back to deterministic mean-based behavior if the R package is unavailable.
