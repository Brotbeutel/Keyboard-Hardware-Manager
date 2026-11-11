"""SQLite database lifecycle and schema migrations."""
from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_VERSION = 1


class Database:
    """Owns a SQLite connection and applies ordered schema migrations."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA busy_timeout = 5000")
        self.migrate()

    def migrate(self) -> None:
        current = int(self.connection.execute("PRAGMA user_version").fetchone()[0])
        if current > SCHEMA_VERSION:
            raise RuntimeError(
                f"Database schema version {current} is newer than supported version {SCHEMA_VERSION}."
            )
        if current < 1:
            with self.connection:
                self.connection.executescript(
                    """
                    CREATE TABLE devices (
                        instance_id TEXT PRIMARY KEY,
                        name TEXT,
                        manufacturer TEXT,
                        device_class TEXT,
                        class_guid TEXT,
                        enumerator TEXT,
                        vid TEXT,
                        pid TEXT,
                        status TEXT NOT NULL CHECK(status IN ('connected','disconnected','unknown')),
                        container_id TEXT,
                        serial_number TEXT,
                        parent_instance_id TEXT,
                        location_paths_json TEXT NOT NULL DEFAULT '[]',
                        first_observed_at TEXT,
                        last_connected_observed_at TEXT,
                        last_disconnected_observed_at TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );

                    CREATE TABLE hardware_ids (
                        instance_id TEXT NOT NULL REFERENCES devices(instance_id) ON DELETE CASCADE,
                        ordinal INTEGER NOT NULL,
                        hardware_id TEXT NOT NULL,
                        PRIMARY KEY(instance_id, ordinal),
                        UNIQUE(instance_id, hardware_id)
                    );

                    CREATE TABLE windows_metadata (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        instance_id TEXT NOT NULL REFERENCES devices(instance_id) ON DELETE CASCADE,
                        property_key TEXT NOT NULL,
                        value TEXT NOT NULL,
                        source TEXT NOT NULL,
                        value_type TEXT NOT NULL,
                        captured_at TEXT NOT NULL
                    );

                    CREATE INDEX idx_windows_metadata_instance
                        ON windows_metadata(instance_id, property_key);

                    CREATE TABLE observations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        instance_id TEXT NOT NULL REFERENCES devices(instance_id) ON DELETE CASCADE,
                        observed_at TEXT NOT NULL,
                        status TEXT NOT NULL CHECK(status IN ('connected','disconnected','unknown')),
                        source TEXT NOT NULL,
                        detail TEXT
                    );

                    CREATE INDEX idx_observations_instance_time
                        ON observations(instance_id, observed_at DESC);
                    CREATE INDEX idx_devices_status ON devices(status);
                    PRAGMA user_version = 1;
                    """
                )

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()
