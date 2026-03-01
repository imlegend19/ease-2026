"""Minimal smoke test to verify settings and MongoDB connectivity."""

from ease2026.core.mongo import get_mongo_client, get_mongo_database
from ease2026.core.settings import settings


def main() -> None:
    _ = settings
    client = get_mongo_client()
    client.admin.command("ping")
    database = get_mongo_database()
    print(database.name)


if __name__ == "__main__":
    main()

