# Artifacts for Replication Package

This folder contains both publishable replication outputs and local execution by-products. For a GitHub release, publish only the files needed to reproduce and verify the paper results while excluding local execution by-products and redundant snapshots.

## Publish to GitHub

Include (under a dataset directory, for example `artifacts/smartshark_2_2/`):

- `artifacts/<dataset_name>/outputs/csv/heroes/**`
- Hero classification outputs (technical, social, hybrid categories).
- `artifacts/<dataset_name>/outputs/csv/analysis/final_tables/**`
- Final table data reported in the paper.
- `artifacts/<dataset_name>/outputs/csv/analysis/rq3_outcomes/**`
- RQ3 bug-fix/reopen outcome tables by severity and fixer role.
- `artifacts/<dataset_name>/outputs/csv/analysis/rq3_inferential/**`
- Inferential statistics artifacts (Kendall tau, Spearman rho, Scott-Knott ESD inputs/results).
- `artifacts/<dataset_name>/outputs/csv/analysis/robustness/threshold_sweep_master.csv`
- Master threshold sweep summary used for robustness reporting (sanitized paths only).
- `artifacts/<dataset_name>/outputs/csv/analysis/robustness/reviewer_*.csv`
- Reviewer-requested robustness summaries.
- `artifacts/<dataset_name>/outputs/plots/analysis/final_figures/**`
- Paper figures (PNG/SVG).
- `artifacts/<dataset_name>/outputs/plots/analysis/reviewer_robustness/**`
- Reviewer robustness figures.

## Do Not Publish

Exclude:

- `artifacts/<dataset_name>/cache/**`
- Local cache/state only. Not required for replication.
- `artifacts/<dataset_name>/runs/**`
- Full parameter-sweep run snapshots. Redundant with `outputs/`.
- `artifacts/<dataset_name>/outputs/csv/analysis/robustness/threshold_sweep_master.pre_neighborhood_backup.csv`
- Backup/intermediate file.

## Package Hygiene

- No absolute machine paths in published artifacts.
- No usernames, hostnames, tokens, or secrets in published files.
- Keep developer records pseudonymous (`author_id`-style IDs) and do not add real names/emails.

## Reproduction Note

Researchers can reproduce the experiment by running the project pipelines from source and using the published dataset-scoped `outputs/` files as expected-result references for tables, figures, and statistical checks.
