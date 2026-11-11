import sys
from datetime import timezone

import pytest

from jkeebs_hardware_manager.discovery.setupapi import (
    DiscoveryError,
    RawPnpDevice,
    RawPnpScan,
    RegistryValue,
    WindowsPnpDiscovery,
    categorize_device,
    parse_usb_vid_pid,
)


class FakeBackend:
    def __init__(self, scan):
        self._scan = scan

    def scan(self):
        return self._scan


def test_parse_vid_pid_only_from_usb_identifier_with_both_values():
    assert parse_usb_vid_pid(
        [r"USB\VID_046A&PID_C33C&REV_0100"],
    ) == ("046A", "C33C")


def test_parse_vid_pid_accepts_compatible_usb_id():
    assert parse_usb_vid_pid(
        [],
        [r"USB\VID_ABCD&PID_1234"],
    ) == ("ABCD", "1234")


@pytest.mark.parametrize("identifiers", [
    [r"HID\VID_046A&PID_C33C"],
    [r"USB\VID_046A"],
    [r"USB\PID_C33C"],
    [r"PCI\VEN_1234&DEV_5678"],
])
def test_parse_vid_pid_does_not_guess_non_usb_or_partial_ids(identifiers):
    assert parse_usb_vid_pid(identifiers) == (None, None)


def test_discovery_maps_present_and_historic_devnodes_without_merging():
    present_id = r"USB\VID_046A&PID_C33C\\A"
    absent_id = r"USB\VID_046A&PID_C33C\\B"
    raw = RawPnpScan(
        devices=(
            RawPnpDevice(
                instance_id=present_id,
                properties={
                    "SPDRP_FRIENDLYNAME": RegistryValue("Keyboard", 1),
                    "SPDRP_CLASS": RegistryValue("Keyboard", 1),
                    "SPDRP_ENUMERATOR_NAME": RegistryValue("USB", 1),
                    "SPDRP_HARDWAREID": RegistryValue((r"USB\VID_046A&PID_C33C",), 7),
                    "SPDRP_BASE_CONTAINERID": RegistryValue("{container}", 1),
                    "SPDRP_LOCATION_PATHS": RegistryValue((r"PCIROOT(0)#USBROOT(0)",), 7),
                },
                parent_instance_id=r"USB\ROOT_HUB30\\1",
                status_flags=8,
                problem_code=0,
            ),
            RawPnpDevice(instance_id=absent_id, properties={
                "SPDRP_CLASS": RegistryValue("Keyboard", 1),
                "SPDRP_HARDWAREID": RegistryValue((r"USB\VID_046A&PID_C33C",), 7),
            }),
        ),
        present_instance_ids=frozenset({present_id}),
        present_scan_complete=True,
    )
    result = WindowsPnpDiscovery(FakeBackend(raw)).discover()

    assert len(result.devices) == 2
    connected, disconnected = result.devices
    assert connected.record.status == "connected"
    assert disconnected.record.status == "disconnected"
    assert connected.record.vid_pid == "046A:C33C"
    assert connected.record.container_id == "{container}"
    assert connected.record.parent_instance_id == r"USB\ROOT_HUB30\\1"
    assert connected.record.location_paths == (r"PCIROOT(0)#USBROOT(0)",)
    assert connected.category == "keyboard"
    assert len({item.record.instance_id for item in result.devices}) == 2
    assert any(item.property_key == "SPDRP_FRIENDLYNAME" for item in connected.windows_metadata)
    assert connected.windows_metadata[0].captured_at.tzinfo == timezone.utc


def test_incomplete_presence_snapshot_keeps_unmatched_status_unknown():
    raw = RawPnpScan(
        devices=(RawPnpDevice(instance_id="ROOT\\DEVICE"),),
        present_instance_ids=frozenset(),
        present_scan_complete=False,
        errors=(DiscoveryError("presence_scan", "incomplete"),),
    )
    result = WindowsPnpDiscovery(FakeBackend(raw)).discover()
    assert result.devices[0].record.status == "unknown"
    assert result.errors[0].operation == "presence_scan"


def test_mapping_error_isolated_to_single_devnode():
    class BadRaw:
        instance_id = "ROOT\\BAD"
        properties = {"SPDRP_FRIENDLYNAME": object()}
        parent_instance_id = None
        status_flags = None
        problem_code = None

    raw = RawPnpScan(
        devices=(BadRaw(), RawPnpDevice(instance_id="ROOT\\GOOD")),
        present_instance_ids=frozenset(),
        present_scan_complete=True,
    )
    result = WindowsPnpDiscovery(FakeBackend(raw)).discover()
    assert len(result.devices) == 1
    assert result.devices[0].record.instance_id == "ROOT\\GOOD"
    assert result.errors[0].instance_id == "ROOT\\BAD"


def test_categories_preserve_raw_classification():
    from jkeebs_hardware_manager.domain.models import DeviceRecord

    assert categorize_device(DeviceRecord(instance_id="USB\\X", device_class="USB")) == "usb"
    assert categorize_device(DeviceRecord(instance_id="HID\\X", device_class="HIDClass")) == "hid"
    assert categorize_device(DeviceRecord(instance_id="ROOT\\X", device_class="Keyboard")) == "keyboard"
    assert categorize_device(DeviceRecord(instance_id="ROOT\\X", device_class="System")) == "other"


@pytest.mark.windows_integration
@pytest.mark.skipif(sys.platform != "win32", reason="SetupAPI integration test requires Windows.")
def test_setupapi_enumerates_pnp_without_admin_requirement():
    result = WindowsPnpDiscovery().discover()
    assert result.present_scan_complete
    assert result.devices
    assert all(device.record.instance_id for device in result.devices)

@pytest.mark.parametrize(("raw", "expected"), [
    (("A\x00B\x00\x00").encode("utf-16-le"), ("A", "B")),
])
def test_decode_multi_string_registry_property(raw, expected):
    from jkeebs_hardware_manager.discovery.setupapi import REG_MULTI_SZ, SetupApiBackend

    assert SetupApiBackend._decode_registry_value(raw, REG_MULTI_SZ) == expected


def test_decode_dword_registry_property_as_decimal_string():
    from jkeebs_hardware_manager.discovery.setupapi import REG_DWORD, SetupApiBackend

    assert SetupApiBackend._decode_registry_value((42).to_bytes(4, "little"), REG_DWORD) == "42"
