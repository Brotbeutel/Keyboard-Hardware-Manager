from datetime import datetime, timedelta, timezone

import pytest

from jkeebs_hardware_manager.domain.models import DeviceObservation, DeviceRecord, WindowsMetadata
from jkeebs_hardware_manager.persistence.database import Database
from jkeebs_hardware_manager.persistence.repositories import (
    DeviceRepository, MetadataRepository, ObservationRepository,
)


@pytest.fixture
def repositories():
    database = Database(":memory:")
    yield (
        database,
        DeviceRepository(database.connection),
        MetadataRepository(database.connection),
        ObservationRepository(database.connection),
    )
    database.close()


def sample_device(**changes):
    values = dict(
        instance_id=r"USB\VID_046A&PID_C33C\ABC123",
        name="Example Keyboard", manufacturer="Example",
        device_class="Keyboard", vid="046a", pid="c33c",
        status="connected", container_id="container-a",
        serial_number="serial-a", hardware_ids=(r"USB\VID_046A&PID_C33C",),
    )
    values.update(changes)
    return DeviceRecord(**values)


def test_empty_database_returns_no_devices(repositories):
    _, devices, _, _ = repositories
    assert devices.list() == []


def test_device_round_trip_and_vid_pid_normalization(repositories):
    _, devices, _, _ = repositories
    devices.upsert(sample_device())
    loaded = devices.get(sample_device().instance_id)
    assert loaded is not None
    assert loaded.vid_pid == "046A:C33C"
    assert loaded.hardware_ids == sample_device().hardware_ids
    assert loaded.container_id == "container-a"
    assert loaded.serial_number == "serial-a"


def test_upsert_uses_instance_id_and_does_not_merge_interfaces(repositories):
    _, devices, _, _ = repositories
    first = sample_device(instance_id="USB\\INTERFACE_A")
    second = sample_device(instance_id="USB\\INTERFACE_B")
    devices.upsert(first)
    devices.upsert(second)
    assert len(devices.list()) == 2


def test_missing_fields_remain_missing(repositories):
    _, devices, _, _ = repositories
    device = DeviceRecord(instance_id="ROOT\\UNKNOWN", status="unknown")
    devices.upsert(device)
    loaded = devices.get(device.instance_id)
    assert loaded is not None
    assert loaded.vid is None and loaded.pid is None
    assert loaded.manufacturer is None


def test_metadata_keeps_source_and_capture_time(repositories):
    _, devices, metadata, _ = repositories
    device = sample_device()
    devices.upsert(device)
    captured = datetime(2026, 1, 2, 3, 4, tzinfo=timezone(timedelta(hours=2)))
    metadata.add(device.instance_id, WindowsMetadata(
        property_key="DEVPKEY_Device_FriendlyName", value="Keyboard",
        source="SetupAPI", captured_at=captured,
    ))
    loaded = metadata.list_for_device(device.instance_id)[0]
    assert loaded.source == "SetupAPI"
    assert loaded.captured_at == captured.astimezone(timezone.utc)


def test_observations_track_separate_first_last_connected_disconnected(repositories):
    _, devices, _, observations = repositories
    device = sample_device()
    devices.upsert(device)
    first = datetime(2026, 2, 1, tzinfo=timezone.utc)
    second = first + timedelta(hours=1)
    third = second + timedelta(hours=1)
    observations.record(DeviceObservation(device.instance_id, first, "connected"))
    observations.record(DeviceObservation(device.instance_id, second, "disconnected"))
    observations.record(DeviceObservation(device.instance_id, third, "connected"))
    loaded = devices.get(device.instance_id)
    assert loaded is not None
    assert loaded.first_observed_at == first
    assert loaded.last_connected_observed_at == third
    assert loaded.last_disconnected_observed_at == second
    assert loaded.status == "connected"
    assert len(observations.list_for_device(device.instance_id)) == 3


def test_naive_timestamps_are_rejected():
    with pytest.raises(ValueError):
        DeviceObservation("USB\\DEVICE", datetime(2026, 1, 1), "connected")


def test_delete_removes_only_app_record_and_cascades_history(repositories):
    _, devices, metadata, observations = repositories
    device = sample_device()
    devices.upsert(device)
    observations.record(DeviceObservation(device.instance_id, datetime.now(timezone.utc), "connected"))
    metadata.add(device.instance_id, WindowsMetadata(
        property_key="test", value="x", source="test",
    ))
    assert devices.delete(device.instance_id) is True
    assert devices.delete(device.instance_id) is False
    assert devices.get(device.instance_id) is None
    assert observations.list_for_device(device.instance_id) == []
    assert metadata.list_for_device(device.instance_id) == []

def test_out_of_order_observations_do_not_rewind_current_status(repositories):
    _, devices, _, observations = repositories
    device = sample_device(status="unknown")
    devices.upsert(device)
    earlier = datetime(2026, 3, 1, tzinfo=timezone.utc)
    later = earlier + timedelta(hours=2)
    observations.record(DeviceObservation(device.instance_id, later, "connected"))
    observations.record(DeviceObservation(device.instance_id, earlier, "disconnected"))
    loaded = devices.get(device.instance_id)
    assert loaded is not None
    assert loaded.status == "connected"
    assert loaded.first_observed_at == earlier
    assert loaded.last_connected_observed_at == later
    assert loaded.last_disconnected_observed_at == earlier


def test_unknown_observation_does_not_erase_connection_timestamps(repositories):
    _, devices, _, observations = repositories
    device = sample_device(status="unknown")
    devices.upsert(device)
    connected = datetime(2026, 4, 1, tzinfo=timezone.utc)
    unknown = connected + timedelta(minutes=5)
    observations.record(DeviceObservation(device.instance_id, connected, "connected"))
    observations.record(DeviceObservation(device.instance_id, unknown, "unknown"))
    loaded = devices.get(device.instance_id)
    assert loaded is not None
    assert loaded.status == "unknown"
    assert loaded.last_connected_observed_at == connected

def test_repeated_upsert_updates_one_devnode_record(repositories):
    _, devices, _, _ = repositories
    device = sample_device(name="Initial name")
    devices.upsert(device)
    devices.upsert(sample_device(name="Updated name", manufacturer="Updated maker"))
    assert len(devices.list()) == 1
    loaded = devices.get(device.instance_id)
    assert loaded is not None
    assert loaded.name == "Updated name"
    assert loaded.manufacturer == "Updated maker"


def test_status_filter_returns_only_matching_devices(repositories):
    _, devices, _, _ = repositories
    devices.upsert(sample_device(instance_id="USB\\CONNECTED", status="connected"))
    devices.upsert(sample_device(instance_id="USB\\DISCONNECTED", status="disconnected"))
    assert [item.status for item in devices.list(status="connected")] == ["connected"]
