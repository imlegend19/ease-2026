## Analysis CSV Artifacts

This folder contains migrated post-hero-analysis outputs from SANER scripts
(`avg_time_pickles.py`, `fixed_issues.py`, `reopened_issues.py`,
`rq2_jaccard.py`, `rq3_scott-knot.py`, `rq3_kendall-tau.py`).

### `issue_metrics/`

- `fixed_<severity>_percentages.csv`
- `reopened_<severity>_percentages.csv`

Schema:

- `severity`: `all|minor|major|critical|trivial|blocker`
- `hero_code`: one of `S1,S2,T1,T2,T3,TS1..TS6,ST1..ST6,SH1..SH6`
- `project_name`: project identifier
- `fixed_percentage` or `reopened_percentage`: percentage value

### `resolution_time/`

- `avg_resolution_time_hours_<severity>.csv`

Schema:

- `severity`: `minor|major|critical|trivial|blocker`
- `hero_code`: hero category code
- `project_name`: project identifier
- `avg_resolution_time_hours`: average issue-resolution time in hours

### `rq2/`

- `final_mean_jaccard_matrix.csv`: 23x23 hero-type matrix of mean Jaccard overlap
- `jaccard_pairs_sorted.csv`: pairwise Jaccard values sorted descending
- `cluster_level_mean_jaccard_matrix.csv`: cluster-level matrix over `ST,S,T,TS,SH`

### `rq3/`

- `mean_ranking_fixed.csv`
- `mean_ranking_reopened.csv`
- `kendall_tau_fixed.csv`
- `kendall_tau_reopened.csv`
- `kendall_tau_p_values_fixed.csv`
- `kendall_tau_p_values_reopened.csv`
- `kendall_tau_formatted_fixed.csv`
- `kendall_tau_formatted_reopened.csv`
- `sk_esd/sk_esd_input_<metric>_<severity>.csv`
- `sk_esd/sk_esd_ranking_<metric>_<severity>.csv`

Ranking schema:

- `metric`: `fixed|reopened`
- `severity`: severity level
- `rank`: mean-based rank position
- `hero_code`: hero category code
- `mean_value`: mean metric value over common projects
- `common_project_count`: number of projects used for that severity ranking

SK-ESD ranking schema:

- `metric`: `fixed|reopened`
- `severity`: severity level
- `hero_code`: hero category code
- `rank`: Scott-Knott rank (or fallback rank)
- `method`: `sk_esd` or `mean_fallback`
