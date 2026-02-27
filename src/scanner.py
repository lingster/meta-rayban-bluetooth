#!/usr/bin/env python3
"""
Bluetooth Scanner for Meta Ray-Ban Smart Glasses

This script scans for Bluetooth devices and identifies Meta Ray-Ban glasses
based on name patterns and manufacturer data.
"""

import asyncio
import argparse
import struct
from dataclasses import dataclass
from typing import Optional, Dict, List, Any
from datetime import datetime

from compat import address_type_label, is_macos, warn_classic_unsupported

try:
    from bleak import BleakScanner, BLEDevice, AdvertisementData
    from bleak.backends.device import BLEDevice
except ImportError:
    print("Error: bleak is required. Install with: uv sync")
    exit(1)

# Known Meta/Facebook Bluetooth Company IDs
META_COMPANY_IDS = {
    0x0397,  # Meta Platforms, Inc.
    0x0157,  # Facebook, Inc. (older)
}

# Ray-Ban glasses name patterns
RAYBAN_NAME_PATTERNS = [
    "ray-ban",
    "rayban", 
    "ray ban",
    "stories",
    "meta",
]

@dataclass
class DeviceInfo:
    """Parsed device information"""
    address: str
    name: Optional[str]
    rssi: int
    is_meta_device: bool
    is_rayban: bool
    manufacturer_data: Dict[int, bytes]
    service_uuids: List[str]
    service_data: Dict[str, bytes]
    tx_power: Optional[int]
    raw_advertisement: Optional[AdvertisementData]
    first_seen: datetime
    last_seen: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "address": self.address,
            "name": self.name,
            "rssi": self.rssi,
            "is_meta_device": self.is_meta_device,
            "is_rayban": self.is_rayban,
            "manufacturer_data": {
                hex(k): v.hex() for k, v in self.manufacturer_data.items()
            },
            "service_uuids": self.service_uuids,
            "service_data": {
                k: v.hex() for k, v in self.service_data.items()
            },
            "tx_power": self.tx_power,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
        }


class MetaRayBanScanner:
    """Scanner to find Meta Ray-Ban smart glasses"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.devices: Dict[str, DeviceInfo] = {}
        self.found_rayban: List[DeviceInfo] = []
        
    def _is_meta_device(self, manufacturer_data: Dict[int, bytes]) -> bool:
        """Check if device has Meta manufacturer data"""
        return any(cid in META_COMPANY_IDS for cid in manufacturer_data.keys())
    
    def _is_rayban(self, name: Optional[str], manufacturer_data: Dict[int, bytes]) -> bool:
        """Check if device is likely Ray-Ban glasses"""
        # Check name
        if name:
            name_lower = name.lower()
            if any(pattern in name_lower for pattern in RAYBAN_NAME_PATTERNS):
                return True
        
        # Check for Meta manufacturer data (strong indicator)
        if self._is_meta_device(manufacturer_data):
            return True
            
        return False
    
    def _parse_manufacturer_data(self, company_id: int, data: bytes) -> Dict[str, Any]:
        """Parse manufacturer-specific data"""
        parsed = {
            "company_id": hex(company_id),
            "raw": data.hex(),
            "length": len(data),
        }
        
        # Try to parse Meta-specific format (speculative)
        if company_id in META_COMPANY_IDS and len(data) >= 2:
            parsed["type"] = data[0]
            parsed["payload"] = data[1:].hex()
            
        return parsed
    
    def _detection_callback(
        self, 
        device: BLEDevice, 
        advertisement_data: AdvertisementData
    ):
        """Callback for each detected device"""
        now = datetime.now()
        
        # Extract data
        manufacturer_data = advertisement_data.manufacturer_data or {}
        service_uuids = advertisement_data.service_uuids or []
        service_data = advertisement_data.service_data or {}
        
        is_meta = self._is_meta_device(manufacturer_data)
        is_rayban = self._is_rayban(device.name, manufacturer_data)
        
        # Create or update device info
        if device.address in self.devices:
            info = self.devices[device.address]
            info.last_seen = now
            info.rssi = advertisement_data.rssi or info.rssi
            if device.name and not info.name:
                info.name = device.name
            # Update manufacturer data if we got more
            info.manufacturer_data.update(manufacturer_data)
            info.service_uuids = list(set(info.service_uuids + service_uuids))
        else:
            info = DeviceInfo(
                address=device.address,
                name=device.name,
                rssi=advertisement_data.rssi or -100,
                is_meta_device=is_meta,
                is_rayban=is_rayban,
                manufacturer_data=manufacturer_data,
                service_uuids=service_uuids,
                service_data=service_data,
                tx_power=advertisement_data.tx_power,
                raw_advertisement=advertisement_data,
                first_seen=now,
                last_seen=now,
            )
            self.devices[device.address] = info
            
            # Track Ray-Ban devices
            if is_rayban:
                self.found_rayban.append(info)
                self._print_rayban_found(info)
        
        # Verbose output
        if self.verbose and (is_meta or is_rayban):
            self._print_device(info)
    
    def _print_device(self, info: DeviceInfo):
        """Print device details"""
        print(f"\n{'='*60}")
        print(f"📱 {info.name or 'Unknown'}")
        print(f"   Address: {info.address}")
        print(f"   RSSI: {info.rssi} dBm")
        print(f"   Meta Device: {'✅' if info.is_meta_device else '❌'}")
        print(f"   Ray-Ban: {'✅' if info.is_rayban else '❌'}")
        
        if info.manufacturer_data:
            print("   Manufacturer Data:")
            for cid, data in info.manufacturer_data.items():
                company_name = "Meta" if cid in META_COMPANY_IDS else f"0x{cid:04X}"
                print(f"      [{company_name}]: {data.hex()}")
                
        if info.service_uuids:
            print("   Service UUIDs:")
            for uuid in info.service_uuids:
                print(f"      - {uuid}")
                
        if info.tx_power:
            print(f"   TX Power: {info.tx_power} dBm")
            
    def _print_rayban_found(self, info: DeviceInfo):
        """Announce Ray-Ban device found"""
        print(f"\n🕶️  FOUND RAY-BAN GLASSES: {info.name or info.address}")
        print(f"    Address: {info.address}")
        print(f"    RSSI: {info.rssi} dBm")
        
    async def scan(self, duration: float = 30.0) -> List[DeviceInfo]:
        """
        Scan for BLE devices
        
        Args:
            duration: Scan duration in seconds
            
        Returns:
            List of DeviceInfo for Ray-Ban devices found
        """
        print(f"🔍 Scanning for Meta Ray-Ban glasses ({duration}s)...")
        print("   Looking for devices with:")
        print("   - Name containing 'Ray-Ban', 'Stories', 'Meta'")
        print(f"   - Meta manufacturer ID: {', '.join(hex(x) for x in META_COMPANY_IDS)}")
        print()
        
        scanner = BleakScanner(detection_callback=self._detection_callback)
        
        await scanner.start()
        await asyncio.sleep(duration)
        await scanner.stop()
        
        print(f"\n{'='*60}")
        print(f"📊 Scan Complete")
        print(f"   Total devices seen: {len(self.devices)}")
        print(f"   Meta devices: {sum(1 for d in self.devices.values() if d.is_meta_device)}")
        print(f"   Ray-Ban devices: {len(self.found_rayban)}")
        if is_macos():
            print(f"\n   ℹ️  On macOS, device addresses are CoreBluetooth UUIDs,")
            print(f"      not hardware MAC addresses.")

        return self.found_rayban
    
    async def scan_classic(self) -> List[Dict[str, Any]]:
        """
        Scan for Classic Bluetooth devices (requires pybluez)
        """
        if warn_classic_unsupported():
            return []

        try:
            import bluetooth
        except ImportError:
            print("⚠️  pybluez not installed. Classic Bluetooth scan unavailable.")
            print("   Install with: uv add pybluez")
            return []

        print("🔍 Scanning for Classic Bluetooth devices...")
        
        try:
            devices = bluetooth.discover_devices(
                duration=8,
                lookup_names=True,
                lookup_class=True,
                flush_cache=True,
            )
            
            results = []
            for addr, name, device_class in devices:
                # Parse device class
                major_class = (device_class >> 8) & 0x1F
                minor_class = (device_class >> 2) & 0x3F
                
                is_audio = major_class == 0x04  # Audio/Video
                is_wearable = major_class == 0x07  # Wearable
                
                info = {
                    "address": addr,
                    "name": name,
                    "device_class": hex(device_class),
                    "major_class": major_class,
                    "minor_class": minor_class,
                    "is_audio": is_audio,
                    "is_wearable": is_wearable,
                    "is_rayban": self._is_rayban(name, {}),
                }
                results.append(info)
                
                if is_audio or is_wearable or info["is_rayban"]:
                    print(f"\n🎧 {name or 'Unknown'} ({addr})")
                    print(f"   Class: {hex(device_class)} (Major: {major_class}, Minor: {minor_class})")
                    
            return results
            
        except Exception as e:
            print(f"❌ Classic scan error: {e}")
            return []


async def main():
    parser = argparse.ArgumentParser(
        description="Scan for Meta Ray-Ban smart glasses"
    )
    parser.add_argument(
        "-d", "--duration",
        type=float,
        default=30.0,
        help="Scan duration in seconds (default: 30)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output for all Meta devices"
    )
    parser.add_argument(
        "--classic",
        action="store_true",
        help="Also scan Classic Bluetooth (requires pybluez)"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        help="Output file for results (JSON)"
    )
    
    args = parser.parse_args()
    
    scanner = MetaRayBanScanner(verbose=args.verbose)
    
    # BLE scan
    rayban_devices = await scanner.scan(duration=args.duration)
    
    # Classic scan
    if args.classic:
        print()
        classic_devices = await scanner.scan_classic()
    
    # Output results
    if rayban_devices:
        print(f"\n🕶️  Found {len(rayban_devices)} Ray-Ban device(s):")
        for device in rayban_devices:
            print(f"\n   {device.name or 'Unknown'}")
            print(f"   Address: {device.address}")
            print(f"   Use this address with connect.py to explore services")
    else:
        print("\n❌ No Ray-Ban devices found")
        print("   Make sure your glasses are:")
        print("   - Powered on")
        print("   - Out of the case")
        print("   - In pairing/discoverable mode")
        
    # Save to file
    if args.output:
        import json
        with open(args.output, 'w') as f:
            json.dump({
                "scan_time": datetime.now().isoformat(),
                "duration": args.duration,
                "rayban_devices": [d.to_dict() for d in rayban_devices],
                "all_devices": [d.to_dict() for d in scanner.devices.values()],
            }, f, indent=2)
        print(f"\n💾 Results saved to {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
