## CSV Snapshot

These CSVs are committed as reproducibility snapshots for the migrated EASE 2026 pipelines.

### Snapshot context

- Source DB URI came from `.env` (`SMARTSHARK_MONGO_URI`).
- Source DB name came from `.env` (`SMARTSHARK_MONGO_DB`).
- At generation time, the following collections had zero records:
  - `final_identity`
  - `comments_with_issue_and_project_info`
  - `commit_with_project_info`

As a result, each CSV currently contains header rows only.

To regenerate with populated data, run the script CLIs listed in the project `README.md`.

