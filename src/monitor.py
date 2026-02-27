#!/usr/bin/env python3
"""
Real-time Bluetooth Monitor for Meta Ray-Ban Glasses

This script connects to the glasses and monitors all notifications,
logging them for later analysis.
"""

import asyncio
import argparse
import json
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

try:
    from bleak import BleakClient, BleakGATTCharacteristic
    from bleak.exc import BleakError
except ImportError:
    print("Error: bleak is required. Install with: pip install bleak")
    exit(1)


class BluetoothMonitor:
    """Monitor Bluetooth communications in real-time"""
    
    def __init__(self, address: str, output_file: Optional[str] = None):
        self.address = address
        self.output_file = output_file
        self.client: Optional[BleakClient] = None
        self.packets: List[Dict[str, Any]] = []
        self.start_time: float = 0
        self.running = True
        self.subscribed_chars: List[str] = []
        
    def _notification_handler(self, char: BleakGATTCharacteristic, data: bytes):
        """Handle incoming notifications"""
        timestamp = datetime.now().timestamp() - self.start_time
        uuid = str(char.uuid)
        
        packet = {
            "timestamp": timestamp,
            "direction": "rx",
            "characteristic": uuid,
            "data": data.hex(),
            "length": len(data),
        }
        self.packets.append(packet)
        
        # Real-time display
        self._print_packet(packet, data)
    
    def _print_packet(self, packet: Dict[str, Any], raw_data: bytes):
        """Print packet in real-time"""
        ts = packet["timestamp"]
        direction = "◀" if packet["direction"] == "rx" else "▶"
        uuid_short = packet["characteristic"][:8]
        
        # Colorize based on first byte (potential command)
        hex_str = packet["data"]
        
        # Try to decode as ASCII
        ascii_repr = ""
        try:
            decoded = raw_data.decode('utf-8', errors='replace')
            if any(c.isalnum() for c in decoded):
                ascii_repr = f" │ {decoded[:20]}"
        except:
            pass
        
        print(f"[{ts:8.3f}s] {direction} {uuid_short}.. │ {hex_str:<40}{ascii_repr}")
    
    async def connect(self) -> bool:
        """Connect to the device"""
        print(f"🔗 Connecting to {self.address}...")
        
        try:
            self.client = BleakClient(self.address, timeout=30.0)
            await self.client.connect()
            
            if self.client.is_connected:
                print(f"✅ Connected to {self.address}")
                return True
            else:
                print("❌ Connection failed")
                return False
                
        except BleakError as e:
            print(f"❌ Connection error: {e}")
            return False
    
    async def subscribe_all(self):
        """Subscribe to all notifiable characteristics"""
        if not self.client:
            return
        
        print("\n🔔 Subscribing to notifications...")
        
        for service in self.client.services:
            for char in service.characteristics:
                if "notify" in char.properties or "indicate" in char.properties:
                    try:
                        await self.client.start_notify(
                            char.uuid,
                            self._notification_handler
                        )
                        self.subscribed_chars.append(str(char.uuid))
                        print(f"   ✅ {char.uuid}")
                    except Exception as e:
                        print(f"   ⚠️  {char.uuid}: {e}")
        
        print(f"\n📡 Subscribed to {len(self.subscribed_chars)} characteristics")
    
    async def write_and_monitor(self, uuid: str, data: bytes):
        """Write data and capture response"""
        if not self.client:
            return
        
        timestamp = datetime.now().timestamp() - self.start_time
        
        # Log the write
        packet = {
            "timestamp": timestamp,
            "direction": "tx",
            "characteristic": uuid,
            "data": data.hex(),
            "length": len(data),
        }
        self.packets.append(packet)
        self._print_packet(packet, data)
        
        # Perform write
        try:
            await self.client.write_gatt_char(uuid, data)
        except Exception as e:
            print(f"⚠️  Write error: {e}")
    
    async def interactive_mode(self):
        """Interactive command mode"""
        print("\n📝 Interactive Mode")
        print("   Commands:")
        print("   w <uuid> <hex>  - Write hex data to characteristic")
        print("   r <uuid>        - Read characteristic")
        print("   q               - Quit")
        print()
        
        while self.running:
            try:
                line = await asyncio.get_event_loop().run_in_executor(
                    None, 
                    lambda: input("cmd> ")
                )
                
                parts = line.strip().split()
                if not parts:
                    continue
                
                cmd = parts[0].lower()
                
                if cmd == 'q':
                    self.running = False
                    break
                    
                elif cmd == 'w' and len(parts) >= 3:
                    uuid = parts[1]
                    data = bytes.fromhex(parts[2])
                    await self.write_and_monitor(uuid, data)
                    
                elif cmd == 'r' and len(parts) >= 2:
                    uuid = parts[1]
                    try:
                        data = await self.client.read_gatt_char(uuid)
                        print(f"   Read: {data.hex()}")
                    except Exception as e:
                        print(f"   Error: {e}")
                        
            except EOFError:
                break
            except KeyboardInterrupt:
                break
    
    async def monitor(self, duration: Optional[float] = None, interactive: bool = False):
        """Main monitoring loop"""
        self.start_time = datetime.now().timestamp()
        
        print("\n" + "=" * 70)
        print("📡 MONITORING BLUETOOTH TRAFFIC")
        print("=" * 70)
        print(f"{'Time':>10} │ Dir │ {'Characteristic':<12} │ {'Data':<40}")
        print("-" * 70)
        
        if interactive:
            await self.interactive_mode()
        elif duration:
            try:
                await asyncio.sleep(duration)
            except asyncio.CancelledError:
                pass
        else:
            # Run until interrupted
            try:
                while self.running:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                pass
    
    async def disconnect(self):
        """Disconnect and save data"""
        # Unsubscribe
        if self.client and self.client.is_connected:
            for uuid in self.subscribed_chars:
                try:
                    await self.client.stop_notify(uuid)
                except:
                    pass
            
            await self.client.disconnect()
            print("\n🔌 Disconnected")
        
        # Save captured data
        if self.output_file and self.packets:
            output_data = {
                "device": self.address,
                "captured_at": datetime.now().isoformat(),
                "duration_seconds": datetime.now().timestamp() - self.start_time,
                "packet_count": len(self.packets),
                "packets": self.packets,
            }
            
            with open(self.output_file, 'w') as f:
                json.dump(output_data, f, indent=2)
            
            print(f"💾 Saved {len(self.packets)} packets to {self.output_file}")


async def main():
    parser = argparse.ArgumentParser(
        description="Monitor Bluetooth traffic from Meta Ray-Ban glasses"
    )
    parser.add_argument(
        "address",
        type=str,
        help="Bluetooth address of the device"
    )
    parser.add_argument(
        "-d", "--duration",
        type=float,
        help="Monitoring duration in seconds (default: unlimited)"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="capture.json",
        help="Output file for captured packets (default: capture.json)"
    )
    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Enable interactive command mode"
    )
    
    args = parser.parse_args()
    
    monitor = BluetoothMonitor(args.address, args.output)
    
    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        print("\n\n⚠️  Interrupted, saving and disconnecting...")
        monitor.running = False
    
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        if not await monitor.connect():
            return
        
        await monitor.subscribe_all()
        await monitor.monitor(
            duration=args.duration,
            interactive=args.interactive
        )
        
    finally:
        await monitor.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
