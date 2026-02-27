#!/usr/bin/env python3
"""
GATT Service Explorer for Meta Ray-Ban Smart Glasses

This script connects to the glasses and enumerates all GATT services,
characteristics, and descriptors. It also attempts to read values
and subscribe to notifications.
"""

import asyncio
import argparse
import struct
import json
from dataclasses import dataclass, asdict
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime
from pathlib import Path

from compat import format_address_help

try:
    from bleak import BleakClient, BleakGATTCharacteristic
    from bleak.exc import BleakError
except ImportError:
    print("Error: bleak is required. Install with: uv sync")
    exit(1)


# Standard Bluetooth GATT UUIDs
STANDARD_SERVICES = {
    "00001800-0000-1000-8000-00805f9b34fb": "Generic Access",
    "00001801-0000-1000-8000-00805f9b34fb": "Generic Attribute",
    "0000180a-0000-1000-8000-00805f9b34fb": "Device Information",
    "0000180f-0000-1000-8000-00805f9b34fb": "Battery Service",
    "00001812-0000-1000-8000-00805f9b34fb": "HID Service",
    "0000181c-0000-1000-8000-00805f9b34fb": "User Data",
    "0000febe-0000-1000-8000-00805f9b34fb": "Bose (common audio)",
}

STANDARD_CHARACTERISTICS = {
    "00002a00-0000-1000-8000-00805f9b34fb": "Device Name",
    "00002a01-0000-1000-8000-00805f9b34fb": "Appearance",
    "00002a04-0000-1000-8000-00805f9b34fb": "Peripheral Preferred Connection Parameters",
    "00002a19-0000-1000-8000-00805f9b34fb": "Battery Level",
    "00002a24-0000-1000-8000-00805f9b34fb": "Model Number String",
    "00002a25-0000-1000-8000-00805f9b34fb": "Serial Number String",
    "00002a26-0000-1000-8000-00805f9b34fb": "Firmware Revision String",
    "00002a27-0000-1000-8000-00805f9b34fb": "Hardware Revision String",
    "00002a28-0000-1000-8000-00805f9b34fb": "Software Revision String",
    "00002a29-0000-1000-8000-00805f9b34fb": "Manufacturer Name String",
    "00002a50-0000-1000-8000-00805f9b34fb": "PnP ID",
}

STANDARD_DESCRIPTORS = {
    "00002900-0000-1000-8000-00805f9b34fb": "Characteristic Extended Properties",
    "00002901-0000-1000-8000-00805f9b34fb": "Characteristic User Description",
    "00002902-0000-1000-8000-00805f9b34fb": "Client Characteristic Configuration",
    "00002903-0000-1000-8000-00805f9b34fb": "Server Characteristic Configuration",
    "00002904-0000-1000-8000-00805f9b34fb": "Characteristic Presentation Format",
}


@dataclass
class DescriptorInfo:
    uuid: str
    handle: int
    name: str
    value: Optional[bytes]
    value_hex: Optional[str]
    value_decoded: Optional[str]


@dataclass
class CharacteristicInfo:
    uuid: str
    handle: int
    name: str
    properties: List[str]
    value: Optional[bytes]
    value_hex: Optional[str]
    value_decoded: Optional[str]
    descriptors: List[DescriptorInfo]
    is_notifiable: bool
    is_writable: bool
    is_readable: bool


@dataclass
class ServiceInfo:
    uuid: str
    handle: int
    name: str
    is_proprietary: bool
    characteristics: List[CharacteristicInfo]


@dataclass
class DeviceProfile:
    address: str
    name: Optional[str]
    connected_at: str
    services: List[ServiceInfo]
    raw_data: Dict[str, Any]


class GATTExplorer:
    """Explore GATT services on a BLE device"""
    
    def __init__(self, address: str, verbose: bool = False):
        self.address = address
        self.verbose = verbose
        self.client: Optional[BleakClient] = None
        self.profile: Optional[DeviceProfile] = None
        self.notifications: Dict[str, List[bytes]] = {}
        
    def _get_service_name(self, uuid: str) -> str:
        """Get human-readable service name"""
        uuid_lower = uuid.lower()
        if uuid_lower in STANDARD_SERVICES:
            return STANDARD_SERVICES[uuid_lower]
        # Check for Meta-specific patterns
        if "meta" in uuid_lower or "face" in uuid_lower:
            return f"Meta Proprietary ({uuid[:8]})"
        return f"Unknown ({uuid[:8]})"
    
    def _get_characteristic_name(self, uuid: str) -> str:
        """Get human-readable characteristic name"""
        uuid_lower = uuid.lower()
        if uuid_lower in STANDARD_CHARACTERISTICS:
            return STANDARD_CHARACTERISTICS[uuid_lower]
        return f"Unknown ({uuid[:8]})"
    
    def _get_descriptor_name(self, uuid: str) -> str:
        """Get human-readable descriptor name"""
        uuid_lower = uuid.lower()
        if uuid_lower in STANDARD_DESCRIPTORS:
            return STANDARD_DESCRIPTORS[uuid_lower]
        return f"Unknown ({uuid[:8]})"
    
    def _decode_value(self, value: bytes, uuid: str) -> Optional[str]:
        """Attempt to decode characteristic value"""
        if not value:
            return None
            
        # Try string decode for known text characteristics
        text_uuids = [
            "00002a24",  # Model Number
            "00002a25",  # Serial Number
            "00002a26",  # Firmware Revision
            "00002a27",  # Hardware Revision
            "00002a28",  # Software Revision
            "00002a29",  # Manufacturer Name
            "00002a00",  # Device Name
        ]
        
        if any(uuid.lower().startswith(u) for u in text_uuids):
            try:
                return value.decode('utf-8').strip('\x00')
            except:
                pass
        
        # Battery level
        if uuid.lower().startswith("00002a19"):
            if len(value) >= 1:
                return f"{value[0]}%"
        
        # Try generic UTF-8 decode
        try:
            decoded = value.decode('utf-8')
            if decoded.isprintable():
                return decoded
        except:
            pass
            
        return None
    
    def _notification_handler(self, char: BleakGATTCharacteristic, data: bytes):
        """Handle incoming notifications"""
        uuid = str(char.uuid)
        if uuid not in self.notifications:
            self.notifications[uuid] = []
        self.notifications[uuid].append(data)
        
        name = self._get_characteristic_name(uuid)
        print(f"\n📨 Notification from {name}")
        print(f"   UUID: {uuid}")
        print(f"   Data ({len(data)} bytes): {data.hex()}")
        
        decoded = self._decode_value(data, uuid)
        if decoded:
            print(f"   Decoded: {decoded}")
            
    async def connect(self) -> bool:
        """Connect to the device"""
        print(f"🔗 Connecting to {self.address}...")
        
        try:
            self.client = BleakClient(self.address, timeout=30.0)
            await self.client.connect()
            print(f"✅ Connected!")
            return True
        except BleakError as e:
            print(f"❌ Connection failed: {e}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from the device"""
        if self.client and self.client.is_connected:
            await self.client.disconnect()
            print("🔌 Disconnected")
    
    async def explore_services(self) -> List[ServiceInfo]:
        """Enumerate all GATT services and characteristics"""
        if not self.client or not self.client.is_connected:
            print("❌ Not connected")
            return []
        
        services: List[ServiceInfo] = []
        
        print("\n📋 Enumerating GATT Services...")
        print("=" * 70)
        
        for service in self.client.services:
            service_uuid = str(service.uuid)
            service_name = self._get_service_name(service_uuid)
            is_proprietary = service_uuid.lower() not in STANDARD_SERVICES
            
            print(f"\n🔹 Service: {service_name}")
            print(f"   UUID: {service_uuid}")
            print(f"   Handle: {service.handle}")
            print(f"   Proprietary: {'Yes' if is_proprietary else 'No'}")
            
            characteristics: List[CharacteristicInfo] = []
            
            for char in service.characteristics:
                char_uuid = str(char.uuid)
                char_name = self._get_characteristic_name(char_uuid)
                properties = char.properties
                
                print(f"\n   📝 Characteristic: {char_name}")
                print(f"      UUID: {char_uuid}")
                print(f"      Handle: {char.handle}")
                print(f"      Properties: {', '.join(properties)}")
                
                # Try to read value
                value = None
                value_hex = None
                value_decoded = None
                
                if "read" in properties:
                    try:
                        value = await self.client.read_gatt_char(char.uuid)
                        value_hex = value.hex()
                        value_decoded = self._decode_value(value, char_uuid)
                        
                        print(f"      Value ({len(value)} bytes): {value_hex}")
                        if value_decoded:
                            print(f"      Decoded: {value_decoded}")
                    except Exception as e:
                        print(f"      ⚠️  Read failed: {e}")
                
                # Explore descriptors
                descriptors: List[DescriptorInfo] = []
                
                for desc in char.descriptors:
                    desc_uuid = str(desc.uuid)
                    desc_name = self._get_descriptor_name(desc_uuid)
                    
                    desc_value = None
                    desc_hex = None
                    desc_decoded = None
                    
                    try:
                        desc_value = await self.client.read_gatt_descriptor(desc.handle)
                        desc_hex = desc_value.hex()
                        desc_decoded = self._decode_value(desc_value, desc_uuid)
                    except:
                        pass
                    
                    descriptors.append(DescriptorInfo(
                        uuid=desc_uuid,
                        handle=desc.handle,
                        name=desc_name,
                        value=desc_value,
                        value_hex=desc_hex,
                        value_decoded=desc_decoded,
                    ))
                    
                    if self.verbose:
                        print(f"      📎 Descriptor: {desc_name}")
                        print(f"         UUID: {desc_uuid}")
                        if desc_hex:
                            print(f"         Value: {desc_hex}")
                
                characteristics.append(CharacteristicInfo(
                    uuid=char_uuid,
                    handle=char.handle,
                    name=char_name,
                    properties=list(properties),
                    value=value,
                    value_hex=value_hex,
                    value_decoded=value_decoded,
                    descriptors=descriptors,
                    is_notifiable="notify" in properties or "indicate" in properties,
                    is_writable="write" in properties or "write-without-response" in properties,
                    is_readable="read" in properties,
                ))
            
            services.append(ServiceInfo(
                uuid=service_uuid,
                handle=service.handle,
                name=service_name,
                is_proprietary=is_proprietary,
                characteristics=characteristics,
            ))
        
        return services
    
    async def subscribe_notifications(self, duration: float = 30.0):
        """Subscribe to all notifiable characteristics"""
        if not self.client or not self.client.is_connected:
            return
        
        print(f"\n🔔 Subscribing to notifications for {duration}s...")
        
        subscribed = []
        for service in self.client.services:
            for char in service.characteristics:
                if "notify" in char.properties or "indicate" in char.properties:
                    try:
                        await self.client.start_notify(
                            char.uuid, 
                            self._notification_handler
                        )
                        subscribed.append(str(char.uuid))
                        print(f"   ✅ Subscribed to {char.uuid}")
                    except Exception as e:
                        print(f"   ⚠️  Could not subscribe to {char.uuid}: {e}")
        
        if subscribed:
            print(f"\n👂 Listening for notifications... (Press Ctrl+C to stop)")
            try:
                await asyncio.sleep(duration)
            except asyncio.CancelledError:
                pass
            
            # Unsubscribe
            for uuid in subscribed:
                try:
                    await self.client.stop_notify(uuid)
                except:
                    pass
        else:
            print("   No notifiable characteristics found")
    
    async def write_characteristic(
        self, 
        uuid: str, 
        data: bytes, 
        response: bool = True
    ) -> bool:
        """Write to a characteristic"""
        if not self.client or not self.client.is_connected:
            return False
        
        try:
            await self.client.write_gatt_char(uuid, data, response=response)
            print(f"✅ Wrote {len(data)} bytes to {uuid}")
            return True
        except Exception as e:
            print(f"❌ Write failed: {e}")
            return False
    
    def save_profile(self, filepath: str, services: List[ServiceInfo]):
        """Save discovered profile to JSON"""
        
        def serialize(obj):
            if isinstance(obj, bytes):
                return obj.hex()
            if hasattr(obj, '__dict__'):
                return {k: serialize(v) for k, v in obj.__dict__.items() 
                        if not k.startswith('_')}
            if isinstance(obj, list):
                return [serialize(i) for i in obj]
            if isinstance(obj, dict):
                return {k: serialize(v) for k, v in obj.items()}
            return obj
        
        profile_data = {
            "address": self.address,
            "discovered_at": datetime.now().isoformat(),
            "services": serialize(services),
            "notifications_captured": {
                k: [v.hex() for v in vals] 
                for k, vals in self.notifications.items()
            },
        }
        
        with open(filepath, 'w') as f:
            json.dump(profile_data, f, indent=2)
        
        print(f"\n💾 Profile saved to {filepath}")


async def main():
    parser = argparse.ArgumentParser(
        description="Explore GATT services on Meta Ray-Ban glasses"
    )
    parser.add_argument(
        "address",
        type=str,
        help=format_address_help(),
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output including all descriptors"
    )
    parser.add_argument(
        "-n", "--notify",
        type=float,
        default=0,
        help="Subscribe to notifications for N seconds"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        help="Output file for device profile (JSON)"
    )
    parser.add_argument(
        "-w", "--write",
        type=str,
        nargs=2,
        metavar=("UUID", "HEX_DATA"),
        help="Write hex data to characteristic"
    )
    
    args = parser.parse_args()
    
    explorer = GATTExplorer(args.address, verbose=args.verbose)
    
    try:
        if not await explorer.connect():
            return
        
        # Explore services
        services = await explorer.explore_services()
        
        # Write if requested
        if args.write:
            uuid, hex_data = args.write
            data = bytes.fromhex(hex_data)
            await explorer.write_characteristic(uuid, data)
        
        # Subscribe to notifications
        if args.notify > 0:
            await explorer.subscribe_notifications(args.notify)
        
        # Save profile
        if args.output:
            explorer.save_profile(args.output, services)
        
        # Summary
        print("\n" + "=" * 70)
        print("📊 Summary")
        print(f"   Total Services: {len(services)}")
        print(f"   Proprietary Services: {sum(1 for s in services if s.is_proprietary)}")
        total_chars = sum(len(s.characteristics) for s in services)
        print(f"   Total Characteristics: {total_chars}")
        notifiable = sum(
            sum(1 for c in s.characteristics if c.is_notifiable) 
            for s in services
        )
        print(f"   Notifiable: {notifiable}")
        writable = sum(
            sum(1 for c in s.characteristics if c.is_writable) 
            for s in services
        )
        print(f"   Writable: {writable}")
        
    finally:
        await explorer.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
