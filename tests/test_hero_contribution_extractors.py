from ease2026.hero.social import compute_comment_count_contributions
from ease2026.hero.technical import compute_commit_count_contributions


class DummyResolver:
    @staticmethod
    def resolve_person_id(person_id, reverse_identity_map):  # noqa: ANN001,ANN002
        return reverse_identity_map.get(person_id, person_id)


class DummyCollection:
    def __init__(self, docs):  # noqa: ANN001
        self._docs = docs

    def find(self, *_args, **_kwargs):  # noqa: ANN001,ANN002
        return iter(self._docs)


def test_commit_count_deduplicates_commit_ids(monkeypatch) -> None:  # noqa: ANN001
    docs = [
        {"_id": "c1", "author_id": "raw_a", "project_name_info": {"name": "proj"}},
        {"_id": "c1", "author_id": "raw_a", "project_name_info": {"name": "proj"}},
        {"_id": "c2", "author_id": "raw_b", "project_name_info": {"name": "proj"}},
    ]

    monkeypatch.setattr(
        "ease2026.hero.technical.get_mongo_collection",
        lambda _name: DummyCollection(docs),
    )
    counts = compute_commit_count_contributions(
        reverse_identity_map={"raw_a": "canon_a", "raw_b": "canon_b"},
        reverse_identity_resolver=DummyResolver(),
    )

    assert counts == {"proj": {"canon_a": 1, "canon_b": 1}}


def test_comment_count_deduplicates_comment_ids(monkeypatch) -> None:  # noqa: ANN001
    docs = [
        {
            "_id": "cm1",
            "author_id": "raw_a",
            "issue_info": {"project_name_info": {"name": "proj"}},
        },
        {
            "_id": "cm1",
            "author_id": "raw_a",
            "issue_info": {"project_name_info": {"name": "proj"}},
        },
        {
            "_id": "cm2",
            "author_id": "raw_b",
            "issue_info": {"project_name_info": {"name": "proj"}},
        },
    ]

    monkeypatch.setattr(
        "ease2026.hero.social.get_mongo_collection",
        lambda _name: DummyCollection(docs),
    )
    counts = compute_comment_count_contributions(
        reverse_identity_map={"raw_a": "canon_a", "raw_b": "canon_b"},
        reverse_identity_resolver=DummyResolver(),
    )

    assert counts == {"proj": {"canon_a": 1, "canon_b": 1}}
