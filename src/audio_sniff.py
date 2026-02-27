#!/usr/bin/env python3
"""
Audio Protocol Sniffer for Meta Ray-Ban Glasses

Reverse-engineering tool to discover how audio data flows between
the glasses and connected devices. Three approaches:

1. BLE notification monitoring — subscribe to all characteristics and look
   for high-frequency or large-payload notifications (potential audio streams)
2. BLE advertisement monitoring — watch for changes in advertising data
   while audio is active on the glasses
3. macOS PacketLogger guidance — instructions for capturing Classic BT
   audio traffic (HFP/A2DP) at the HCI level

Usage:
    uv run src/audio_sniff.py scan            # Passive BLE ad monitoring
    uv run src/audio_sniff.py connect ADDRESS  # Connect and sniff notifications
    uv run src/audio_sniff.py hci-guide       # macOS PacketLogger instructions
"""

import asyncio
import json
import signal
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from compat import format_address_help, is_macos

try:
    from bleak import BleakClient, BleakGATTCharacteristic, BleakScanner
    from bleak.exc import BleakError
except ImportError:
    print("Error: bleak is required. Install with: uv sync")
    sys.exit(1)

import typer

# Glasses identifiers
GLASSES_ADDRESS = "3B07C626-8BC4-0545-9F27-93137792C31A"
GLASSES_NAME_PATTERNS = ("RB Meta", "Ray-Ban", "Meta")
META_COMPANY_IDS = {0x01AB, 0x0397, 0x0157}

app = typer.Typer(help="Reverse-engineer Meta Ray-Ban glasses audio protocol.")


class NotificationSniffer:
    """Connect to glasses and monitor all notification traffic for audio patterns."""

    def __init__(self, address: str, output_file: str):
        self.address = address
        self.output_file = output_file
        self.client: Optional[BleakClient] = None
        self.running = True
        self.start_time: float = 0
        self.char_stats: dict[str, dict] = defaultdict(
            lambda: {"count": 0, "total_bytes": 0, "first_ts": 0, "last_ts": 0, "samples": []}
        )
        self.packets: list[dict] = []

    def _notification_handler(self, char: BleakGATTCharacteristic, data: bytes):
        ts = time.time() - self.start_time
        uuid = str(char.uuid)
        stats = self.char_stats[uuid]
        stats["count"] += 1
        stats["total_bytes"] += len(data)
        if stats["first_ts"] == 0:
            stats["first_ts"] = ts
        stats["last_ts"] = ts
        if len(stats["samples"]) < 20:
            stats["samples"].append({"ts": ts, "len": len(data), "hex": data.hex()})

        packet = {
            "timestamp": ts,
            "characteristic": uuid,
            "length": len(data),
            "data": data.hex(),
        }
        self.packets.append(packet)

        # Real-time display — highlight potential audio streams
        rate = ""
        if stats["count"] > 1 and (ts - stats["first_ts"]) > 0:
            pps = stats["count"] / (ts - stats["first_ts"])
            bps = stats["total_bytes"] / (ts - stats["first_ts"])
            rate = f" | {pps:.0f} pkt/s  {bps:.0f} B/s"
            # Flag high-throughput characteristics as potential audio
            if pps > 10 or bps > 1000:
                rate += "  ** POSSIBLE AUDIO **"

        uuid_short = uuid[:8]
        print(f"[{ts:8.3f}s] {uuid_short}.. | {len(data):4d}B | {data[:16].hex():<32}{rate}")

    async def connect_and_sniff(self, duration: Optional[float] = None):
        print(f"Connecting to {self.address}...")

        try:
            self.client = BleakClient(self.address, timeout=30.0)
            await self.client.connect()
        except BleakError as exc:
            print(f"Connection failed: {exc}")
            print("\nTroubleshooting:")
            print("  - Put glasses in charging case, hold button 5s until blue LED")
            print("  - Ensure glasses are not connected to another device")
            print("  - Try: uv run src/audio_sniff.py scan  (passive monitoring)")
            return

        if not self.client.is_connected:
            print("Connection failed.")
            return

        print(f"Connected! Enumerating services...\n")

        # Enumerate and subscribe
        subscribed = []
        for service in self.client.services:
            for char in service.characteristics:
                props = char.properties
                print(f"  {char.uuid}  [{', '.join(props)}]")
                if "notify" in props or "indicate" in props:
                    try:
                        await self.client.start_notify(char.uuid, self._notification_handler)
                        subscribed.append(str(char.uuid))
                    except Exception as exc:
                        print(f"    -> subscribe failed: {exc}")

        print(f"\nSubscribed to {len(subscribed)} characteristics")
        print("=" * 80)
        print("Monitoring notifications... (trigger audio on glasses now)")
        print("  - Say 'Hey Meta' to activate voice assistant")
        print("  - Play music through the glasses")
        print("  - Make a phone call")
        print("  - Press the capture button")
        print("=" * 80)
        print()

        self.start_time = time.time()

        try:
            if duration:
                await asyncio.sleep(duration)
            else:
                while self.running:
                    await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            pass

        # Cleanup
        for uuid in subscribed:
            try:
                await self.client.stop_notify(uuid)
            except Exception:
                pass
        await self.client.disconnect()

        self._print_analysis()
        self._save_results()

    def _print_analysis(self):
        print("\n" + "=" * 80)
        print("NOTIFICATION ANALYSIS")
        print("=" * 80)

        if not self.char_stats:
            print("No notifications received.")
            return

        # Sort by total bytes (most data = most likely audio)
        sorted_chars = sorted(
            self.char_stats.items(),
            key=lambda x: x[1]["total_bytes"],
            reverse=True,
        )

        print(f"\n{'Characteristic':<40} {'Packets':>8} {'Bytes':>10} {'Rate':>12}")
        print("-" * 75)

        for uuid, stats in sorted_chars:
            elapsed = stats["last_ts"] - stats["first_ts"]
            rate_str = ""
            if elapsed > 0:
                bps = stats["total_bytes"] / elapsed
                rate_str = f"{bps:.0f} B/s"
            marker = " <-- AUDIO?" if stats["total_bytes"] > 5000 else ""
            print(f"{uuid[:38]:<40} {stats['count']:>8} {stats['total_bytes']:>10} {rate_str:>12}{marker}")

    def _save_results(self):
        if not self.packets:
            return

        results = {
            "device": self.address,
            "captured_at": datetime.now().isoformat(),
            "duration_seconds": time.time() - self.start_time if self.start_time else 0,
            "packet_count": len(self.packets),
            "characteristic_summary": {
                uuid: {
                    "count": s["count"],
                    "total_bytes": s["total_bytes"],
                    "samples": s["samples"],
                }
                for uuid, s in self.char_stats.items()
            },
            "packets": self.packets,
        }

        with open(self.output_file, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nSaved {len(self.packets)} packets to {self.output_file}")

    def stop(self):
        self.running = False


class AdvertisementMonitor:
    """Passively monitor BLE advertisements from the glasses."""

    def __init__(self, output_file: str, target_address: Optional[str] = None):
        self.output_file = output_file
        self.target_address = target_address
        self.running = True
        self.start_time = time.time()
        self.ad_log: list[dict] = []
        self.seen_data: dict[str, str] = {}

    def _is_glasses(self, name: Optional[str], manufacturer_data: dict) -> bool:
        if name and any(p.lower() in name.lower() for p in GLASSES_NAME_PATTERNS):
            return True
        for company_id in manufacturer_data:
            if company_id in META_COMPANY_IDS:
                return True
        return False

    async def monitor(self, duration: Optional[float] = None):
        print("Scanning for Meta Ray-Ban BLE advertisements...")
        print("Watching for changes in advertising data while audio is active.")
        print("=" * 80)

        def _detection_callback(device, advertising_data):
            name = advertising_data.local_name or device.name
            mfr = advertising_data.manufacturer_data

            is_target = False
            if self.target_address and device.address == self.target_address:
                is_target = True
            elif self._is_glasses(name, mfr):
                is_target = True

            if not is_target:
                return

            ts = time.time() - self.start_time

            # Serialize current ad data
            ad_snapshot = {
                "name": name,
                "rssi": advertising_data.rssi,
                "manufacturer_data": {
                    hex(k): v.hex() for k, v in mfr.items()
                },
                "service_uuids": [str(u) for u in (advertising_data.service_uuids or [])],
                "service_data": {
                    str(k): v.hex() for k, v in (advertising_data.service_data or {}).items()
                },
                "tx_power": advertising_data.tx_power,
            }

            snapshot_key = json.dumps(ad_snapshot, sort_keys=True)
            prev = self.seen_data.get(device.address)

            changed = prev is not None and prev != snapshot_key
            self.seen_data[device.address] = snapshot_key

            marker = " ** CHANGED **" if changed else ""
            print(
                f"[{ts:8.1f}s] {device.address[:12]}.. "
                f"RSSI={advertising_data.rssi:>4} "
                f"mfr={list(ad_snapshot['manufacturer_data'].values())}"
                f"{marker}"
            )

            entry = {"timestamp": ts, "address": device.address, "changed": changed}
            entry.update(ad_snapshot)
            self.ad_log.append(entry)

        scanner = BleakScanner(detection_callback=_detection_callback)
        await scanner.start()

        try:
            if duration:
                await asyncio.sleep(duration)
            else:
                while self.running:
                    await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            pass
        finally:
            await scanner.stop()

        self._save_results()

    def _save_results(self):
        if not self.ad_log:
            print("\nNo glasses advertisements captured.")
            return

        with open(self.output_file, "w") as f:
            json.dump(
                {
                    "captured_at": datetime.now().isoformat(),
                    "target_address": self.target_address,
                    "entries": self.ad_log,
                },
                f,
                indent=2,
            )
        print(f"\nSaved {len(self.ad_log)} advertisement entries to {self.output_file}")

    def stop(self):
        self.running = False


def _print_hci_guide():
    """Print instructions for capturing Classic BT audio traffic on macOS."""
    print("""
================================================================================
  macOS Bluetooth HCI Packet Capture Guide
================================================================================

The glasses use Classic Bluetooth (A2DP/HFP) for audio, not BLE.
To capture audio protocol traffic, use Apple's PacketLogger or sysdiagnose.

OPTION 1: Apple Bluetooth PacketLogger (Recommended)
-----------------------------------------------------
1. Download from: https://developer.apple.com/download/all/
   Search for "Additional Tools for Xcode" — PacketLogger is inside.

2. Open PacketLogger.app

3. It automatically captures HCI traffic from the Mac's Bluetooth controller.

4. Pair/connect the glasses to this Mac via System Settings > Bluetooth
   (put glasses in case, hold button 5s for pairing mode)

5. Once connected, trigger audio:
   - Play music routed to the glasses
   - Say "Hey Meta"
   - Make a phone call

6. In PacketLogger, filter for:
   - SCO/eSCO packets (voice audio — HFP calls)
   - L2CAP with PSM=0x0019 (AVDTP — A2DP streaming)
   - SDP records (to see which profiles the glasses advertise)

7. Export as .pklg or .pcap for analysis in Wireshark

OPTION 2: sysdiagnose (simpler, less detailed)
-----------------------------------------------
   sudo log collect --last 5m --output bt_log.logarchive

OPTION 3: Bluetooth Explorer (if available)
--------------------------------------------
   Part of Additional Tools for Xcode. Lets you browse SDP records
   and see which Classic BT profiles (A2DP, HFP, AVRCP) the glasses support.

WHAT TO LOOK FOR:
-----------------
- SDP Service Records: lists all Classic BT profiles the glasses support
  - A2DP Sink/Source (audio streaming)
  - HFP (hands-free/call audio)
  - AVRCP (media controls)
  - SPP (Serial Port Profile — possible proprietary data channel)

- AVDTP signaling: codec negotiation (SBC, AAC, aptX, LDAC?)
  - The codec config tells us sample rate, bitrate, channel mode

- SCO connection parameters: voice codec (CVSD, mSBC, LC3?)

- Any proprietary L2CAP PSM or RFCOMM channel for Meta-specific commands

- Look for the sequence of events when "Hey Meta" is activated:
  1. What BLE notification triggers?
  2. Does a new SCO link open?
  3. What data flows on the proprietary channel?

KEY INSIGHT:
------------
Audio almost certainly flows over Classic BT (not BLE). BLE is likely
used only for control/signaling (start recording, voice assistant trigger).
The actual audio PCM/codec data goes over:
  - A2DP (AVDTP/L2CAP) for music playback
  - HFP (SCO/eSCO) for voice/calls
  - Possibly a proprietary SCO or L2CAP channel for mic capture

================================================================================
""")


@app.command()
def scan(
    duration: Optional[float] = typer.Option(None, "--duration", "-d", help="Scan duration in seconds"),
    output: str = typer.Option("ad_monitor.json", "--output", "-o", help="Output file"),
    address: Optional[str] = typer.Option(GLASSES_ADDRESS, "--address", "-a", help="Target device address"),
):
    """Passively monitor BLE advertisements from the glasses."""
    monitor = AdvertisementMonitor(output_file=output, target_address=address)

    def _handle_signal(_sig, _frame):
        print("\nStopping scan...")
        monitor.stop()

    signal.signal(signal.SIGINT, _handle_signal)

    asyncio.run(monitor.monitor(duration=duration))


@app.command()
def connect(
    address: str = typer.Argument(GLASSES_ADDRESS, help="Device address (CoreBluetooth UUID on macOS)"),
    duration: Optional[float] = typer.Option(None, "--duration", "-d", help="Monitoring duration in seconds"),
    output: str = typer.Option("audio_sniff.json", "--output", "-o", help="Output file"),
):
    """Connect to glasses and monitor all BLE notifications for audio patterns."""
    sniffer = NotificationSniffer(address=address, output_file=output)

    def _handle_signal(_sig, _frame):
        print("\nStopping sniffer...")
        sniffer.stop()

    signal.signal(signal.SIGINT, _handle_signal)

    asyncio.run(sniffer.connect_and_sniff(duration=duration))


@app.command(name="hci-guide")
def hci_guide():
    """Print instructions for capturing Classic BT audio traffic on macOS."""
    _print_hci_guide()


if __name__ == "__main__":
    app()
