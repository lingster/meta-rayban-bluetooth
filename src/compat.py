#!/usr/bin/env python3
"""
Platform utilities for macOS/Linux compatibility.

macOS CoreBluetooth returns UUIDs instead of MAC addresses for BLE devices,
and Classic Bluetooth scanning via pybluez is not supported.
"""

import sys


def is_macos() -> bool:
    """Check if running on macOS."""
    return sys.platform == "darwin"


def format_address_help() -> str:
    """Return platform-appropriate address format hint for CLI help text."""
    if is_macos():
        return "Device address (CoreBluetooth UUID, e.g. 12345678-1234-1234-1234-123456789ABC)"
    return "Device address (MAC format XX:XX:XX:XX:XX:XX)"


def address_type_label() -> str:
    """Short label describing the address type on this platform."""
    return "CoreBluetooth UUID" if is_macos() else "MAC address"


def warn_classic_unsupported() -> bool:
    """Print a warning if Classic BT scanning is unsupported on this platform.

    Returns True if unsupported (caller should skip), False otherwise.
    """
    if is_macos():
        print("⚠️  Classic Bluetooth scanning is not supported on macOS.")
        print("   macOS does not expose the HCI interface needed by pybluez.")
        print("   Use BLE scanning instead (-d flag).")
        return True
    return False
