"""Windows PnP discovery adapters."""

from .setupapi import (
    DiscoveredDevice,
    DiscoveryError,
    DiscoveryResult,
    WindowsPnpDiscovery,
    categorize_device,
    parse_usb_vid_pid,
)

__all__ = [
    "DiscoveredDevice",
    "DiscoveryError",
    "DiscoveryResult",
    "WindowsPnpDiscovery",
    "categorize_device",
    "parse_usb_vid_pid",
]
