from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class ProfileStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS external_profiles (
                    subject TEXT PRIMARY KEY,
                    preferred_username TEXT,
                    email TEXT,
                    full_name TEXT,
                    identity_provider TEXT NOT NULL,
                    profile_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.commit()

    def upsert(self, subject: str, identity_provider: str, profile: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO external_profiles (
                    subject,
                    preferred_username,
                    email,
                    full_name,
                    identity_provider,
                    profile_json,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(subject) DO UPDATE SET
                    preferred_username = excluded.preferred_username,
                    email = excluded.email,
                    full_name = excluded.full_name,
                    identity_provider = excluded.identity_provider,
                    profile_json = excluded.profile_json,
                    updated_at = excluded.updated_at
                """,
                (
                    subject,
                    profile.get("preferred_username") or profile.get("login"),
                    profile.get("email") or profile.get("default_email"),
                    profile.get("name")
                    or profile.get("real_name")
                    or profile.get("display_name")
                    or profile.get("given_name")
                    or profile.get("first_name"),
                    identity_provider,
                    json.dumps(profile, ensure_ascii=True, sort_keys=True),
                ),
            )
            connection.commit()
