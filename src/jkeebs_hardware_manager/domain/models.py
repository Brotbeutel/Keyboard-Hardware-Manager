"""Immutable domain models shared by discovery and persistence layers."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal


DeviceStatus = Literal["connected", "disconnected", "unknown"]


def utc_iso(value: datetime) -> str:
    """Return an aware datetime as an ISO-8601 UTC timestamp."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timestamps must be timezone-aware.")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    """Parse a stored ISO-8601 timestamp and normalize it to UTC."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Stored timestamps must include a timezone.")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class WindowsMetadata:
    """A Windows-provided value with its origin and meaning kept explicit."""
    property_key: str
    value: str
    source: str
    value_type: str = "string"
    captured_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.property_key.strip():
            raise ValueError("property_key must not be empty.")
        if not self.source.strip():
            raise ValueError("source must not be empty.")
        utc_iso(self.captured_at)


@dataclass(frozen=True, slots=True)
class DeviceRecord:
    """One PnP devnode/interface; physical-device grouping is deliberately separate."""
    instance_id: str
    name: str | None = None
    manufacturer: str | None = None
    device_class: str | None = None
    class_guid: str | None = None
    enumerator: str | None = None
    vid: str | None = None
    pid: str | None = None
    status: DeviceStatus = "unknown"
    container_id: str | None = None
    serial_number: str | None = None
    parent_instance_id: str | None = None
    location_paths: tuple[str, ...] = ()
    hardware_ids: tuple[str, ...] = ()
    first_observed_at: datetime | None = None
    last_connected_observed_at: datetime | None = None
    last_disconnected_observed_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.instance_id.strip():
            raise ValueError("instance_id must not be empty.")
        if self.status not in ("connected", "disconnected", "unknown"):
            raise ValueError(f"Unsupported device status: {self.status}")
        for value in (self.vid, self.pid):
            if value is not None and (len(value) != 4 or any(c not in "0123456789abcdefABCDEF" for c in value)):
                raise ValueError("VID and PID must be four hexadecimal characters.")
        for timestamp in (
            self.first_observed_at, self.last_connected_observed_at,
            self.last_disconnected_observed_at, self.created_at, self.updated_at,
        ):
            if timestamp is not None:
                utc_iso(timestamp)

    @property
    def vid_pid(self) -> str | None:
        if self.vid is None or self.pid is None:
            return None
        return f"{self.vid.upper()}:{self.pid.upper()}"


@dataclass(frozen=True, slots=True)
class DeviceObservation:
    """An app observation of a devnode at a specific scan time."""
    instance_id: str
    observed_at: datetime
    status: DeviceStatus
    source: str = "app_scan"
    detail: str | None = None

    def __post_init__(self) -> None:
        if not self.instance_id.strip():
            raise ValueError("instance_id must not be empty.")
        if self.status not in ("connected", "disconnected", "unknown"):
            raise ValueError(f"Unsupported observation status: {self.status}")
        if not self.source.strip():
            raise ValueError("source must not be empty.")
        utc_iso(self.observed_at)
