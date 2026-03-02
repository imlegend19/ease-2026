# SANER Legacy Parity Audit (EASE-2026)

Date: 2026-03-02

## Scope

This audit compares `experiments/ease-2026` against `experiments/saner-2026-legacy` for
preprocessing and methodology choices that materially affect results.

## Implemented parity fixes

1. Canonical person IDs are now resolved through `final_identity` reverse mapping across
   technical/social hero extraction and RQ3 outcomes.
2. Commit-count and comment-count extraction now de-duplicate by record ID (legacy behavior),
   preventing accidental double-count inflation.

## Fundamental differences and decision

1. Hero top-k rounding:
   - Legacy: `int(top_fraction * n)` (floor), can yield `0` selected contributors.
   - EASE: `ceil(top_fraction * n)` with minimum `1`.
   - Decision: keep EASE behavior as methodologically correct for "top 20%" interpretation.

2. RQ2 overlap computation:
   - Legacy: mean per-project Jaccard over intersecting project set.
   - EASE: global project-author pair Jaccard.
   - Decision: keep EASE behavior for direct set-overlap interpretation in final tables.

3. RQ3 fixed/reopen definitions:
   - Legacy: event-level fixed counting (can exceed 100%), mixed issue types.
   - EASE: issue-level bug-only outcomes with bounded rates.
   - Decision: keep EASE behavior as correct for reviewer-defensible outcome semantics.

4. RQ1 prevalence denominator:
   - Legacy RQ1 pipeline: denominator derived from projects appearing in hero memberships.
   - EASE: denominator from full `project` collection (dataset scope).
   - Decision: keep EASE behavior as correct prevalence denominator.

5. Severity ordering:
   - Legacy and EASE use different output ordering.
   - Decision: presentation-only difference; no semantic change.

## If strict SANER reproduction is required

Use the legacy pipeline behavior end-to-end (including rounding, overlap aggregation, and issue
metric definitions). EASE currently keeps SANER parity for identity handling and dedup counting,
but intentionally keeps improved methodology for RQ outputs.
