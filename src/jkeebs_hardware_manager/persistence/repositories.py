"""Repository operations for devices, Windows metadata and app observations."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Iterable

from jkeebs_hardware_manager.domain.models import (
    DeviceObservation, DeviceRecord, WindowsMetadata, parse_utc, utc_iso,
)


class DeviceRepository:
    """Persists PnP devnodes independently; it never merges by display name or VID/PID."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def upsert(self, device: DeviceRecord) -> None:
        now = datetime.now(timezone.utc)
        created = utc_iso(device.created_at)
        updated = utc_iso(device.updated_at or now)
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO devices (
                    instance_id,name,manufacturer,device_class,class_guid,enumerator,vid,pid,status,
                    container_id,serial_number,parent_instance_id,location_paths_json,
                    first_observed_at,last_connected_observed_at,last_disconnected_observed_at,
                    created_at,updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(instance_id) DO UPDATE SET
                    name=excluded.name, manufacturer=excluded.manufacturer,
                    device_class=excluded.device_class, class_guid=excluded.class_guid,
                    enumerator=excluded.enumerator, vid=excluded.vid, pid=excluded.pid,
                    status=excluded.status, container_id=excluded.container_id,
                    serial_number=excluded.serial_number, parent_instance_id=excluded.parent_instance_id,
                    location_paths_json=excluded.location_paths_json,
                    first_observed_at=COALESCE(devices.first_observed_at, excluded.first_observed_at),
                    last_connected_observed_at=COALESCE(excluded.last_connected_observed_at, devices.last_connected_observed_at),
                    last_disconnected_observed_at=COALESCE(excluded.last_disconnected_observed_at, devices.last_disconnected_observed_at),
                    updated_at=excluded.updated_at
                """,
                (
                    device.instance_id, device.name, device.manufacturer, device.device_class,
                    device.class_guid, device.enumerator, device.vid.upper() if device.vid else None,
                    device.pid.upper() if device.pid else None, device.status, device.container_id,
                    device.serial_number, device.parent_instance_id, json.dumps(device.location_paths),
                    utc_iso(device.first_observed_at) if device.first_observed_at else None,
                    utc_iso(device.last_connected_observed_at) if device.last_connected_observed_at else None,
                    utc_iso(device.last_disconnected_observed_at) if device.last_disconnected_observed_at else None,
                    created, updated,
                ),
            )
            self.connection.execute("DELETE FROM hardware_ids WHERE instance_id = ?", (device.instance_id,))
            self.connection.executemany(
                "INSERT INTO hardware_ids(instance_id, ordinal, hardware_id) VALUES(?,?,?)",
                [(device.instance_id, index, value) for index, value in enumerate(dict.fromkeys(device.hardware_ids))],
            )

    def get(self, instance_id: str) -> DeviceRecord | None:
        row = self.connection.execute(
            "SELECT * FROM devices WHERE instance_id = ?", (instance_id,)
        ).fetchone()
        return self._to_model(row) if row else None

    def list(self, status: str | None = None) -> list[DeviceRecord]:
        if status is not None and status not in ("connected", "disconnected", "unknown"):
            raise ValueError(f"Unsupported device status: {status}")
        if status is None:
            rows = self.connection.execute("SELECT * FROM devices ORDER BY name COLLATE NOCASE, instance_id").fetchall()
        else:
            rows = self.connection.execute(
                "SELECT * FROM devices WHERE status = ? ORDER BY name COLLATE NOCASE, instance_id", (status,)
            ).fetchall()
        return [self._to_model(row) for row in rows]

    def delete(self, instance_id: str) -> bool:
        """Delete only this application's record and its dependent history."""
        with self.connection:
            cursor = self.connection.execute("DELETE FROM devices WHERE instance_id = ?", (instance_id,))
        return cursor.rowcount > 0

    def _to_model(self, row: sqlite3.Row) -> DeviceRecord:
        hardware_ids = self.connection.execute(
            "SELECT hardware_id FROM hardware_ids WHERE instance_id = ? ORDER BY ordinal",
            (row["instance_id"],),
        ).fetchall()
        return DeviceRecord(
            instance_id=row["instance_id"], name=row["name"], manufacturer=row["manufacturer"],
            device_class=row["device_class"], class_guid=row["class_guid"], enumerator=row["enumerator"],
            vid=row["vid"], pid=row["pid"], status=row["status"], container_id=row["container_id"],
            serial_number=row["serial_number"], parent_instance_id=row["parent_instance_id"],
            location_paths=tuple(json.loads(row["location_paths_json"])),
            hardware_ids=tuple(item["hardware_id"] for item in hardware_ids),
            first_observed_at=parse_utc(row["first_observed_at"]) if row["first_observed_at"] else None,
            last_connected_observed_at=parse_utc(row["last_connected_observed_at"]) if row["last_connected_observed_at"] else None,
            last_disconnected_observed_at=parse_utc(row["last_disconnected_observed_at"]) if row["last_disconnected_observed_at"] else None,
            created_at=parse_utc(row["created_at"]), updated_at=parse_utc(row["updated_at"]),
        )


class MetadataRepository:
    """Stores Windows properties with explicit source, type and capture time."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def add(self, instance_id: str, metadata: WindowsMetadata) -> int:
        with self.connection:
            cursor = self.connection.execute(
                """INSERT INTO windows_metadata
                   (instance_id,property_key,value,source,value_type,captured_at)
                   VALUES(?,?,?,?,?,?)""",
                (instance_id, metadata.property_key, metadata.value, metadata.source,
                 metadata.value_type, utc_iso(metadata.captured_at)),
            )
        return int(cursor.lastrowid)

    def list_for_device(self, instance_id: str) -> list[WindowsMetadata]:
        rows = self.connection.execute(
            """SELECT property_key,value,source,value_type,captured_at
               FROM windows_metadata WHERE instance_id = ? ORDER BY captured_at,id""",
            (instance_id,),
        ).fetchall()
        return [
            WindowsMetadata(
                property_key=row["property_key"], value=row["value"], source=row["source"],
                value_type=row["value_type"], captured_at=parse_utc(row["captured_at"]),
            )
            for row in rows
        ]


class ObservationRepository:
    """App-observed connection states; timestamps are never treated as Windows metadata."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def record(self, observation: DeviceObservation) -> int:
        timestamp = utc_iso(observation.observed_at)
        with self.connection:
            cursor = self.connection.execute(
                """INSERT INTO observations(instance_id,observed_at,status,source,detail)
                   VALUES(?,?,?,?,?)""",
                (observation.instance_id, timestamp, observation.status, observation.source, observation.detail),
            )
            self.connection.execute(
                """
                UPDATE devices SET
                    first_observed_at = CASE
                        WHEN first_observed_at IS NULL OR first_observed_at > ? THEN ?
                        ELSE first_observed_at END,
                    last_connected_observed_at = CASE
                        WHEN ? = 'connected' AND (last_connected_observed_at IS NULL OR last_connected_observed_at < ?)
                        THEN ? ELSE last_connected_observed_at END,
                    last_disconnected_observed_at = CASE
                        WHEN ? = 'disconnected' AND (last_disconnected_observed_at IS NULL OR last_disconnected_observed_at < ?)
                        THEN ? ELSE last_disconnected_observed_at END,
                    status = CASE
                        WHEN last_observed_at IS NULL OR last_observed_at <= ? THEN ? ELSE status END,
                    last_observed_at = CASE
                        WHEN last_observed_at IS NULL OR last_observed_at < ? THEN ? ELSE last_observed_at END,
                    updated_at = CASE WHEN updated_at < ? THEN ? ELSE updated_at END
                WHERE instance_id = ?
                """,
                (timestamp, timestamp,
                 observation.status, timestamp, timestamp,
                 observation.status, timestamp, timestamp,
                 timestamp, observation.status,
                 timestamp, timestamp, timestamp, timestamp, observation.instance_id),
            )
        return int(cursor.lastrowid)

    def list_for_device(self, instance_id: str) -> list[DeviceObservation]:
        rows = self.connection.execute(
            """SELECT instance_id,observed_at,status,source,detail FROM observations
               WHERE instance_id = ? ORDER BY observed_at,id""",
            (instance_id,),
        ).fetchall()
        return [
            DeviceObservation(
                instance_id=row["instance_id"], observed_at=parse_utc(row["observed_at"]),
                status=row["status"], source=row["source"], detail=row["detail"],
            )
            for row in rows
        ]
