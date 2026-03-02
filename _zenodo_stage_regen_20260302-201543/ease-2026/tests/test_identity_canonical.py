from ease2026.identity.canonical import (
    load_identity_context,
    normalize_identifier,
    resolve_canonical_person_id,
)


class DummyResolver:
    @staticmethod
    def resolve_person_id(person_id, reverse_identity_map):  # noqa: ANN001,ANN002
        return reverse_identity_map.get(person_id, person_id)


def test_normalize_identifier_handles_empty_values() -> None:
    assert normalize_identifier(None) is None
    assert normalize_identifier("  ") is None
    assert normalize_identifier(" x ") == "x"


def test_resolve_canonical_person_id_uses_reverse_map() -> None:
    assert (
        resolve_canonical_person_id(
            person_id="raw",
            reverse_identity_map={"raw": "merged"},
            reverse_identity_resolver=DummyResolver(),
        )
        == "merged"
    )


def test_load_identity_context_prefers_provided_map() -> None:
    provided_map = {"a": "b"}
    loaded_map, resolver = load_identity_context(
        reverse_identity_map=provided_map,
        reverse_identity_resolver=DummyResolver(),
    )
    assert loaded_map is provided_map
    assert isinstance(resolver, DummyResolver)
