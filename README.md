# EASE 2026 (Fresh Workspace)

This workspace restarts the EASE-2026 experiments from scratch.

## Kept Baseline

- `.env` SmartSHARK connection settings
- `src/ease2026/core/` shared helpers
- `src/ease2026/identity/` identity cache helpers

## Setup

From this directory:

```powershell
uv lock
uv sync
```

## Notes

- Add new pipelines and analyses incrementally for the revised EASE-2026 direction.
- Smoke test Mongo connectivity:
  - `python -m ease2026.cli.run_smoke`
- Generate inferential RQ3 artifacts (Kendall tau + Scott-Knott ESD via Docker):
  - `python -m ease2026.cli.compute_rq3_inferential --fixer both`
