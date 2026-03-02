"""Canonical person-id helpers backed by SmartSHARK final_identity."""

from __future__ import annotations

from typing import Any

from ease2026.identity.reverse_identity import ReverseIdentityMap, ReverseIdentityResolver


def normalize_identifier(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def load_identity_context(
    reverse_identity_map: ReverseIdentityMap | None = None,
    reverse_identity_resolver: ReverseIdentityResolver | None = None,
    *,
    refresh_cache: bool = False,
) -> tuple[ReverseIdentityMap, ReverseIdentityResolver]:
    resolver = reverse_identity_resolver or ReverseIdentityResolver()
    mapping = (
        reverse_identity_map
        if reverse_identity_map is not None
        else resolver.load_or_build(refresh_cache=refresh_cache)
    )
    return mapping, resolver


def resolve_canonical_person_id(
    person_id: Any,
    reverse_identity_map: ReverseIdentityMap,
    reverse_identity_resolver: ReverseIdentityResolver,
) -> str | None:
    resolved_person_id = reverse_identity_resolver.resolve_person_id(
        person_id,
        reverse_identity_map,
    )
    return normalize_identifier(resolved_person_id)
