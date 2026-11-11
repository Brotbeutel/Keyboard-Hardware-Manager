"""Read-only Windows PnP discovery using SetupAPI and CfgMgr32.

The public discovery service accepts an injectable backend so its mapping and
classification logic can be tested without Windows or attached hardware.
"""
from __future__ import annotations

import ctypes
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Mapping, Protocol

from ctypes import wintypes

from jkeebs_hardware_manager.domain.models import DeviceRecord, WindowsMetadata


DIGCF_PRESENT = 0x00000002
DIGCF_ALLCLASSES = 0x00000004
ERROR_INVALID_DATA = 13
ERROR_FILE_NOT_FOUND = 2
ERROR_INSUFFICIENT_BUFFER = 122
ERROR_NO_MORE_ITEMS = 259
CR_SUCCESS = 0
CR_NO_SUCH_DEVNODE = 0x0000000D

REG_SZ = 1
REG_EXPAND_SZ = 2
REG_BINARY = 3
REG_DWORD = 4
REG_MULTI_SZ = 7
REG_QWORD = 11

# SetupAPI SPDRP_* property identifiers. These are legacy registry-backed
# properties, not arbitrary registry paths.
_REGISTRY_PROPERTIES: tuple[tuple[int, str], ...] = (
    (0x00000000, "SPDRP_DEVICEDESC"),
    (0x00000001, "SPDRP_HARDWAREID"),
    (0x00000002, "SPDRP_COMPATIBLEIDS"),
    (0x00000007, "SPDRP_CLASS"),
    (0x00000008, "SPDRP_CLASSGUID"),
    (0x0000000B, "SPDRP_MFG"),
    (0x0000000C, "SPDRP_FRIENDLYNAME"),
    (0x00000016, "SPDRP_ENUMERATOR_NAME"),
    (0x00000023, "SPDRP_LOCATION_PATHS"),
    (0x00000024, "SPDRP_BASE_CONTAINERID"),
)

_REGISTRY_TYPE_NAMES = {
    REG_SZ: "REG_SZ",
    REG_EXPAND_SZ: "REG_EXPAND_SZ",
    REG_BINARY: "REG_BINARY",
    REG_DWORD: "REG_DWORD",
    REG_MULTI_SZ: "REG_MULTI_SZ",
    REG_QWORD: "REG_QWORD",
}

_USB_VID = re.compile(r"VID_([0-9A-F]{4})", re.IGNORECASE)
_USB_PID = re.compile(r"PID_([0-9A-F]{4})", re.IGNORECASE)
_KEYBOARD_CLASS_GUID = "{4D36E96B-E325-11CE-BFC1-08002BE10318}"


@dataclass(frozen=True, slots=True)
class RegistryValue:
    value: str | tuple[str, ...]
    registry_type: int

    @property
    def type_name(self) -> str:
        return _REGISTRY_TYPE_NAMES.get(self.registry_type, f"REG_TYPE_{self.registry_type}")


@dataclass(frozen=True, slots=True)
class RawPnpDevice:
    """A single SetupAPI device-info element before domain mapping."""

    instance_id: str
    properties: Mapping[str, RegistryValue] = field(default_factory=dict)
    parent_instance_id: str | None = None
    status_flags: int | None = None
    problem_code: int | None = None


@dataclass(frozen=True, slots=True)
class RawPnpScan:
    devices: tuple[RawPnpDevice, ...]
    present_instance_ids: frozenset[str]
    present_scan_complete: bool
    errors: tuple["DiscoveryError", ...] = ()


@dataclass(frozen=True, slots=True)
class DiscoveryError:
    operation: str
    message: str
    instance_id: str | None = None
    code: int | None = None


@dataclass(frozen=True, slots=True)
class DiscoveredDevice:
    record: DeviceRecord
    windows_metadata: tuple[WindowsMetadata, ...]
    status_flags: int | None = None
    problem_code: int | None = None

    @property
    def category(self) -> str:
        return categorize_device(self.record)


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    captured_at: datetime
    devices: tuple[DiscoveredDevice, ...]
    errors: tuple[DiscoveryError, ...]
    present_scan_complete: bool


class PnpBackend(Protocol):
    def scan(self) -> RawPnpScan:
        """Return all known devnodes plus a separate current-presence snapshot."""


def _as_string(value: RegistryValue | None) -> str | None:
    if value is None or isinstance(value.value, tuple):
        return None
    return value.value or None


def _as_string_tuple(value: RegistryValue | None) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value.value, tuple):
        return tuple(item for item in value.value if item)
    return (value.value,) if value.value else ()


def parse_usb_vid_pid(
    hardware_ids: tuple[str, ...] | list[str],
    compatible_ids: tuple[str, ...] | list[str] = (),
) -> tuple[str | None, str | None]:
    """Extract VID/PID only from a single USB-prefixed identifier containing both."""
    for identifier in (*hardware_ids, *compatible_ids):
        if not identifier.upper().startswith("USB\\"):
            continue
        vid = _USB_VID.search(identifier)
        pid = _USB_PID.search(identifier)
        if vid and pid:
            return vid.group(1).upper(), pid.group(1).upper()
    return None, None


def categorize_device(record: DeviceRecord) -> str:
    """Return a broad UI category without discarding the raw Windows class."""
    device_class = (record.device_class or "").casefold()
    class_guid = (record.class_guid or "").strip("{}").casefold()
    enumerator = (record.enumerator or "").casefold()
    instance_id = record.instance_id.casefold()

    if device_class == "keyboard" or class_guid == _KEYBOARD_CLASS_GUID.strip("{}").casefold():
        return "keyboard"
    if device_class == "hidclass" or enumerator == "hid" or instance_id.startswith("hid\\"):
        return "hid"
    if device_class == "usb" or enumerator == "usb" or instance_id.startswith("usb\\"):
        return "usb"
    return "other"


class WindowsPnpDiscovery:
    """Map raw SetupAPI results to domain records; no persistence or device changes."""

    def __init__(self, backend: PnpBackend | None = None) -> None:
        self._backend = backend

    def discover(self) -> DiscoveryResult:
        if self._backend is None:
            self._backend = SetupApiBackend()

        captured_at = datetime.now(timezone.utc)
        raw_scan = self._backend.scan()
        discovered: list[DiscoveredDevice] = []
        errors = list(raw_scan.errors)

        for raw in raw_scan.devices:
            try:
                properties = raw.properties
                hardware_ids = _as_string_tuple(properties.get("SPDRP_HARDWAREID"))
                compatible_ids = _as_string_tuple(properties.get("SPDRP_COMPATIBLEIDS"))
                vid, pid = parse_usb_vid_pid(hardware_ids, compatible_ids)

                if raw.instance_id.casefold() in {
                    instance_id.casefold() for instance_id in raw_scan.present_instance_ids
                }:
                    status = "connected"
                elif raw_scan.present_scan_complete:
                    status = "disconnected"
                else:
                    status = "unknown"

                name = (
                    _as_string(properties.get("SPDRP_FRIENDLYNAME"))
                    or _as_string(properties.get("SPDRP_DEVICEDESC"))
                )
                location_paths = _as_string_tuple(properties.get("SPDRP_LOCATION_PATHS"))
                record = DeviceRecord(
                    instance_id=raw.instance_id,
                    name=name,
                    manufacturer=_as_string(properties.get("SPDRP_MFG")),
                    device_class=_as_string(properties.get("SPDRP_CLASS")),
                    class_guid=_as_string(properties.get("SPDRP_CLASSGUID")),
                    enumerator=_as_string(properties.get("SPDRP_ENUMERATOR_NAME")),
                    vid=vid,
                    pid=pid,
                    status=status,
                    container_id=_as_string(properties.get("SPDRP_BASE_CONTAINERID")),
                    parent_instance_id=raw.parent_instance_id,
                    location_paths=location_paths,
                    hardware_ids=hardware_ids,
                    created_at=captured_at,
                    updated_at=captured_at,
                )

                metadata = [
                    WindowsMetadata(
                        property_key=key,
                        value="\\n".join(value.value) if isinstance(value.value, tuple) else value.value,
                        source="SetupAPI:SetupDiGetDeviceRegistryPropertyW",
                        value_type=value.type_name,
                        captured_at=captured_at,
                    )
                    for key, value in properties.items()
                ]
                if raw.parent_instance_id:
                    metadata.append(WindowsMetadata(
                        property_key="CM_Get_Parent",
                        value=raw.parent_instance_id,
                        source="CfgMgr32:CM_Get_Parent+CM_Get_Device_IDW",
                        value_type="device_instance_id",
                        captured_at=captured_at,
                    ))
                if raw.status_flags is not None:
                    metadata.append(WindowsMetadata(
                        property_key="CM_Get_DevNode_Status.status_flags",
                        value=str(raw.status_flags),
                        source="CfgMgr32:CM_Get_DevNode_Status",
                        value_type="DWORD",
                        captured_at=captured_at,
                    ))
                if raw.problem_code is not None:
                    metadata.append(WindowsMetadata(
                        property_key="CM_Get_DevNode_Status.problem_code",
                        value=str(raw.problem_code),
                        source="CfgMgr32:CM_Get_DevNode_Status",
                        value_type="DWORD",
                        captured_at=captured_at,
                    ))

                discovered.append(DiscoveredDevice(
                    record=record,
                    windows_metadata=tuple(metadata),
                    status_flags=raw.status_flags,
                    problem_code=raw.problem_code,
                ))
            except Exception as exc:  # isolate malformed or unexpected per-device data
                errors.append(DiscoveryError(
                    operation="map_device",
                    message=f"{type(exc).__name__}: {exc}",
                    instance_id=raw.instance_id,
                ))

        return DiscoveryResult(
            captured_at=captured_at,
            devices=tuple(discovered),
            errors=tuple(errors),
            present_scan_complete=raw_scan.present_scan_complete,
        )


class _Guid(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class _SpDevinfoData(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("ClassGuid", _Guid),
        ("DevInst", wintypes.DWORD),
        ("Reserved", ctypes.c_size_t),
    ]


class SetupApiBackend:
    """ctypes implementation of SetupAPI/CfgMgr32; read-only and Windows-only."""

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise OSError("SetupAPI discovery is available only on Windows.")

        win_dll = getattr(ctypes, "WinDLL")
        self._setupapi = win_dll("setupapi", use_last_error=True)
        self._cfgmgr32 = win_dll("cfgmgr32", use_last_error=True)
        self._configure_functions()

    def _configure_functions(self) -> None:
        setup = self._setupapi
        setup.SetupDiGetClassDevsW.argtypes = [
            ctypes.POINTER(_Guid), wintypes.LPCWSTR, wintypes.HWND, wintypes.DWORD
        ]
        setup.SetupDiGetClassDevsW.restype = wintypes.HANDLE
        setup.SetupDiEnumDeviceInfo.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(_SpDevinfoData)
        ]
        setup.SetupDiEnumDeviceInfo.restype = wintypes.BOOL
        setup.SetupDiGetDeviceInstanceIdW.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(_SpDevinfoData), wintypes.LPWSTR,
            wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)
        ]
        setup.SetupDiGetDeviceInstanceIdW.restype = wintypes.BOOL
        setup.SetupDiGetDeviceRegistryPropertyW.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(_SpDevinfoData), wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD)
        ]
        setup.SetupDiGetDeviceRegistryPropertyW.restype = wintypes.BOOL
        setup.SetupDiDestroyDeviceInfoList.argtypes = [wintypes.HANDLE]
        setup.SetupDiDestroyDeviceInfoList.restype = wintypes.BOOL

        cfg = self._cfgmgr32
        cfg.CM_Get_Parent.argtypes = [
            ctypes.POINTER(wintypes.ULONG), wintypes.ULONG, wintypes.ULONG
        ]
        cfg.CM_Get_Parent.restype = wintypes.DWORD
        cfg.CM_Get_Device_IDW.argtypes = [
            wintypes.ULONG, wintypes.LPWSTR, wintypes.ULONG, wintypes.ULONG
        ]
        cfg.CM_Get_Device_IDW.restype = wintypes.DWORD
        cfg.CM_Get_DevNode_Status.argtypes = [
            ctypes.POINTER(wintypes.ULONG), ctypes.POINTER(wintypes.ULONG),
            wintypes.ULONG, wintypes.ULONG
        ]
        cfg.CM_Get_DevNode_Status.restype = wintypes.DWORD

    def scan(self) -> RawPnpScan:
        devices, _, all_errors = self._enumerate_device_set(present_only=False, read_properties=True)
        present_devices, present_complete, present_errors = self._enumerate_device_set(
            present_only=True, read_properties=False
        )
        present_ids = frozenset(item.instance_id for item in present_devices)
        return RawPnpScan(
            devices=tuple(devices),
            present_instance_ids=present_ids,
            present_scan_complete=present_complete,
            errors=tuple((*all_errors, *present_errors)),
        )

    def _enumerate_device_set(
        self, *, present_only: bool, read_properties: bool
    ) -> tuple[list[RawPnpDevice], bool, list[DiscoveryError]]:
        flags = DIGCF_ALLCLASSES | (DIGCF_PRESENT if present_only else 0)
        handle = self._setupapi.SetupDiGetClassDevsW(None, None, None, flags)
        invalid_handle = ctypes.c_void_p(-1).value
        if handle is None or handle == invalid_handle:
            code = ctypes.get_last_error()
            return [], False, [DiscoveryError(
                operation="SetupDiGetClassDevsW",
                message=f"Windows error {code}",
                code=code,
            )]

        devices: list[RawPnpDevice] = []
        errors: list[DiscoveryError] = []
        complete = True
        try:
            index = 0
            while True:
                data = _SpDevinfoData()
                data.cbSize = ctypes.sizeof(_SpDevinfoData)
                if not self._setupapi.SetupDiEnumDeviceInfo(handle, index, ctypes.byref(data)):
                    code = ctypes.get_last_error()
                    if code == ERROR_NO_MORE_ITEMS:
                        break
                    errors.append(DiscoveryError(
                        operation="SetupDiEnumDeviceInfo",
                        message=f"Windows error {code}",
                        code=code,
                    ))
                    complete = False
                    break
                index += 1

                instance_id = self._get_instance_id(handle, data)
                if not instance_id:
                    code = ctypes.get_last_error()
                    errors.append(DiscoveryError(
                        operation="SetupDiGetDeviceInstanceIdW",
                        message=f"Windows error {code}; device skipped because it has no readable instance ID",
                        code=code,
                    ))
                    complete = False
                    continue

                if not read_properties:
                    devices.append(RawPnpDevice(instance_id=instance_id))
                    continue

                properties: dict[str, RegistryValue] = {}
                for property_id, property_name in _REGISTRY_PROPERTIES:
                    try:
                        value = self._get_registry_property(handle, data, property_id)
                        if value is not None:
                            properties[property_name] = value
                    except OSError as exc:
                        errors.append(DiscoveryError(
                            operation=property_name,
                            message=str(exc),
                            instance_id=instance_id,
                            code=getattr(exc, "winerror", None),
                        ))

                parent_id = self._get_parent_id(data.DevInst, instance_id, errors)
                status_flags, problem_code = self._get_devnode_status(data.DevInst, instance_id, errors)
                devices.append(RawPnpDevice(
                    instance_id=instance_id,
                    properties=properties,
                    parent_instance_id=parent_id,
                    status_flags=status_flags,
                    problem_code=problem_code,
                ))
        finally:
            self._setupapi.SetupDiDestroyDeviceInfoList(handle)

        return devices, complete, errors

    def _get_instance_id(self, handle: int, data: _SpDevinfoData) -> str | None:
        buffer = ctypes.create_unicode_buffer(4096)
        required = wintypes.DWORD()
        if not self._setupapi.SetupDiGetDeviceInstanceIdW(
            handle, ctypes.byref(data), buffer, len(buffer), ctypes.byref(required)
        ):
            return None
        return buffer.value or None

    def _get_registry_property(
        self, handle: int, data: _SpDevinfoData, property_id: int
    ) -> RegistryValue | None:
        registry_type = wintypes.DWORD()
        required = wintypes.DWORD()
        ok = self._setupapi.SetupDiGetDeviceRegistryPropertyW(
            handle, ctypes.byref(data), property_id, ctypes.byref(registry_type),
            None, 0, ctypes.byref(required)
        )
        if not ok:
            code = ctypes.get_last_error()
            if code in (ERROR_INVALID_DATA, ERROR_FILE_NOT_FOUND) or required.value == 0:
                return None
            if code != ERROR_INSUFFICIENT_BUFFER:
                raise OSError(code, f"SetupDiGetDeviceRegistryPropertyW failed (property 0x{property_id:02X})")

        buffer = ctypes.create_string_buffer(required.value)
        if not self._setupapi.SetupDiGetDeviceRegistryPropertyW(
            handle, ctypes.byref(data), property_id, ctypes.byref(registry_type),
            ctypes.cast(buffer, ctypes.c_void_p), required.value, ctypes.byref(required)
        ):
            code = ctypes.get_last_error()
            raise OSError(code, f"SetupDiGetDeviceRegistryPropertyW failed (property 0x{property_id:02X})")

        raw = buffer.raw[:required.value]
        return RegistryValue(
            value=self._decode_registry_value(raw, registry_type.value),
            registry_type=registry_type.value,
        )

    @staticmethod
    def _decode_registry_value(raw: bytes, registry_type: int) -> str | tuple[str, ...]:
        if registry_type in (REG_SZ, REG_EXPAND_SZ):
            return raw.decode("utf-16-le", errors="replace").rstrip("\x00")
        if registry_type == REG_MULTI_SZ:
            text = raw.decode("utf-16-le", errors="replace").rstrip("\x00")
            return tuple(part for part in text.split("\x00") if part)
        if registry_type == REG_DWORD and len(raw) >= 4:
            return str(int.from_bytes(raw[:4], "little", signed=False))
        if registry_type == REG_QWORD and len(raw) >= 8:
            return str(int.from_bytes(raw[:8], "little", signed=False))
        return raw.hex().upper()

    def _get_parent_id(
        self, devinst: int, instance_id: str, errors: list[DiscoveryError]
    ) -> str | None:
        parent = wintypes.ULONG()
        result = self._cfgmgr32.CM_Get_Parent(ctypes.byref(parent), devinst, 0)
        if result == CR_NO_SUCH_DEVNODE:
            return None
        if result != CR_SUCCESS:
            errors.append(DiscoveryError(
                operation="CM_Get_Parent",
                message=f"Configuration Manager error {result}",
                instance_id=instance_id,
                code=int(result),
            ))
            return None

        buffer = ctypes.create_unicode_buffer(4096)
        result = self._cfgmgr32.CM_Get_Device_IDW(parent.value, buffer, len(buffer), 0)
        if result != CR_SUCCESS:
            errors.append(DiscoveryError(
                operation="CM_Get_Device_IDW",
                message=f"Configuration Manager error {result}",
                instance_id=instance_id,
                code=int(result),
            ))
            return None
        return buffer.value or None

    def _get_devnode_status(
        self, devinst: int, instance_id: str, errors: list[DiscoveryError]
    ) -> tuple[int | None, int | None]:
        status = wintypes.ULONG()
        problem = wintypes.ULONG()
        result = self._cfgmgr32.CM_Get_DevNode_Status(
            ctypes.byref(status), ctypes.byref(problem), devinst, 0
        )
        if result != CR_SUCCESS:
            errors.append(DiscoveryError(
                operation="CM_Get_DevNode_Status",
                message=f"Configuration Manager error {result}",
                instance_id=instance_id,
                code=int(result),
            ))
            return None, None
        return int(status.value), int(problem.value)
