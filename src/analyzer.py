#!/usr/bin/env python3
"""
Bluetooth Packet Analyzer for Meta Ray-Ban Glasses

This script analyzes captured Bluetooth packets to help reverse engineer
the communication protocol.
"""

import argparse
import json
import struct
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from collections import defaultdict
from datetime import datetime


@dataclass
class Packet:
    """Represents a captured Bluetooth packet"""
    timestamp: float
    direction: str  # "tx" or "rx"
    characteristic: str
    data: bytes
    
    @property
    def hex(self) -> str:
        return self.data.hex()
    
    @property
    def length(self) -> int:
        return len(self.data)


class ProtocolAnalyzer:
    """Analyze captured packets to identify patterns"""
    
    def __init__(self):
        self.packets: List[Packet] = []
        self.patterns: Dict[str, List[Tuple[bytes, int]]] = defaultdict(list)
        
    def load_json(self, filepath: str):
        """Load packets from JSON file"""
        with open(filepath) as f:
            data = json.load(f)
        
        for entry in data.get("packets", []):
            self.packets.append(Packet(
                timestamp=entry.get("timestamp", 0),
                direction=entry.get("direction", "unknown"),
                characteristic=entry.get("characteristic", ""),
                data=bytes.fromhex(entry.get("data", "")),
            ))
        
        print(f"📂 Loaded {len(self.packets)} packets")
        
    def add_packet(
        self, 
        data: bytes, 
        characteristic: str = "", 
        direction: str = "rx"
    ):
        """Add a packet for analysis"""
        self.packets.append(Packet(
            timestamp=datetime.now().timestamp(),
            direction=direction,
            characteristic=characteristic,
            data=data,
        ))
    
    def analyze_structure(self) -> Dict[str, Any]:
        """Analyze packet structure patterns"""
        results = {
            "packet_count": len(self.packets),
            "unique_lengths": set(),
            "characteristics_seen": set(),
            "common_prefixes": {},
            "length_distribution": defaultdict(int),
        }
        
        for pkt in self.packets:
            results["unique_lengths"].add(pkt.length)
            results["characteristics_seen"].add(pkt.characteristic)
            results["length_distribution"][pkt.length] += 1
            
            # Track common prefixes (possible command bytes)
            if pkt.length >= 1:
                prefix = pkt.data[0]
                if prefix not in results["common_prefixes"]:
                    results["common_prefixes"][prefix] = {
                        "count": 0,
                        "examples": [],
                    }
                results["common_prefixes"][prefix]["count"] += 1
                if len(results["common_prefixes"][prefix]["examples"]) < 3:
                    results["common_prefixes"][prefix]["examples"].append(pkt.hex)
        
        # Convert sets to lists for JSON serialization
        results["unique_lengths"] = sorted(list(results["unique_lengths"]))
        results["characteristics_seen"] = list(results["characteristics_seen"])
        results["length_distribution"] = dict(results["length_distribution"])
        
        return results
    
    def find_command_response_pairs(self) -> List[Dict[str, Any]]:
        """Try to identify command-response patterns"""
        pairs = []
        
        tx_packets = [p for p in self.packets if p.direction == "tx"]
        rx_packets = [p for p in self.packets if p.direction == "rx"]
        
        for tx in tx_packets:
            # Look for responses within 1 second
            responses = [
                rx for rx in rx_packets 
                if rx.timestamp > tx.timestamp 
                and rx.timestamp - tx.timestamp < 1.0
            ]
            
            if responses:
                pairs.append({
                    "command": tx.hex,
                    "command_char": tx.characteristic,
                    "responses": [
                        {"data": r.hex, "char": r.characteristic}
                        for r in responses[:3]  # Limit to first 3
                    ],
                    "time_delta": responses[0].timestamp - tx.timestamp,
                })
        
        return pairs
    
    def decode_tlv(self, data: bytes) -> List[Dict[str, Any]]:
        """Attempt TLV (Type-Length-Value) decode"""
        tlvs = []
        offset = 0
        
        while offset < len(data):
            if offset + 2 > len(data):
                break
                
            # Try Type (1 byte) + Length (1 byte) format
            type_byte = data[offset]
            length = data[offset + 1]
            
            if offset + 2 + length > len(data):
                # Invalid TLV, might not be TLV format
                break
            
            value = data[offset + 2:offset + 2 + length]
            
            tlvs.append({
                "type": hex(type_byte),
                "length": length,
                "value": value.hex(),
                "offset": offset,
            })
            
            offset += 2 + length
        
        return tlvs if offset == len(data) else []
    
    def guess_protocol_format(self) -> Dict[str, Any]:
        """Attempt to identify the protocol format"""
        guesses = []
        
        for pkt in self.packets[:20]:  # Analyze first 20 packets
            if pkt.length < 2:
                continue
            
            analysis = {
                "data": pkt.hex,
                "length": pkt.length,
                "possible_formats": [],
            }
            
            # Check for TLV
            tlvs = self.decode_tlv(pkt.data)
            if tlvs:
                analysis["possible_formats"].append({
                    "format": "TLV",
                    "parsed": tlvs,
                })
            
            # Check for header + payload (first byte is command)
            if pkt.length >= 2:
                analysis["possible_formats"].append({
                    "format": "CMD_PAYLOAD",
                    "command": hex(pkt.data[0]),
                    "payload": pkt.data[1:].hex(),
                })
            
            # Check for header + length + payload
            if pkt.length >= 3 and pkt.data[1] == pkt.length - 2:
                analysis["possible_formats"].append({
                    "format": "CMD_LEN_PAYLOAD",
                    "command": hex(pkt.data[0]),
                    "length": pkt.data[1],
                    "payload": pkt.data[2:].hex(),
                })
            
            guesses.append(analysis)
        
        return {"packet_analyses": guesses}
    
    def hexdump(self, data: bytes, prefix: str = "") -> str:
        """Create hex dump of data"""
        lines = []
        for i in range(0, len(data), 16):
            chunk = data[i:i+16]
            hex_part = ' '.join(f'{b:02x}' for b in chunk)
            ascii_part = ''.join(
                chr(b) if 32 <= b < 127 else '.' 
                for b in chunk
            )
            lines.append(f"{prefix}{i:04x}  {hex_part:<48}  {ascii_part}")
        return '\n'.join(lines)
    
    def print_analysis(self):
        """Print comprehensive analysis"""
        print("\n" + "=" * 70)
        print("📊 PACKET ANALYSIS")
        print("=" * 70)
        
        structure = self.analyze_structure()
        
        print(f"\n📈 Statistics:")
        print(f"   Total packets: {structure['packet_count']}")
        print(f"   Unique lengths: {structure['unique_lengths']}")
        print(f"   Characteristics: {len(structure['characteristics_seen'])}")
        
        print(f"\n📏 Length Distribution:")
        for length, count in sorted(structure["length_distribution"].items()):
            bar = "█" * min(count, 40)
            print(f"   {length:3d} bytes: {count:4d} {bar}")
        
        print(f"\n🔤 Common First Bytes (possible commands):")
        sorted_prefixes = sorted(
            structure["common_prefixes"].items(),
            key=lambda x: x[1]["count"],
            reverse=True
        )
        for prefix, info in sorted_prefixes[:10]:
            print(f"   0x{prefix:02X}: {info['count']:4d} occurrences")
            for ex in info["examples"]:
                print(f"         Example: {ex}")
        
        # Protocol format guess
        print("\n🔍 Protocol Format Analysis:")
        format_analysis = self.guess_protocol_format()
        for pkt_analysis in format_analysis["packet_analyses"][:5]:
            print(f"\n   Data: {pkt_analysis['data']}")
            for fmt in pkt_analysis["possible_formats"]:
                print(f"   → {fmt['format']}: {fmt}")
        
        # Command-response pairs
        pairs = self.find_command_response_pairs()
        if pairs:
            print("\n🔄 Command-Response Pairs:")
            for pair in pairs[:5]:
                print(f"\n   Command: {pair['command']}")
                print(f"   On char: {pair['command_char']}")
                for resp in pair['responses']:
                    print(f"   Response: {resp['data']}")
                print(f"   Delta: {pair['time_delta']*1000:.1f}ms")
        
        # Hex dumps of interesting packets
        print("\n📜 Sample Hex Dumps:")
        for pkt in self.packets[:5]:
            print(f"\n   [{pkt.direction.upper()}] {pkt.characteristic}")
            print(self.hexdump(pkt.data, prefix="      "))


def create_sample_capture():
    """Create a sample capture file for testing"""
    sample_data = {
        "device": "AA:BB:CC:DD:EE:FF",
        "captured_at": datetime.now().isoformat(),
        "packets": [
            {
                "timestamp": 1000.0,
                "direction": "tx",
                "characteristic": "0000ff01-0000-1000-8000-00805f9b34fb",
                "data": "01"
            },
            {
                "timestamp": 1000.1,
                "direction": "rx",
                "characteristic": "0000ff02-0000-1000-8000-00805f9b34fb",
                "data": "01006400"
            },
            {
                "timestamp": 1001.0,
                "direction": "tx",
                "characteristic": "0000ff01-0000-1000-8000-00805f9b34fb",
                "data": "0210"
            },
            {
                "timestamp": 1001.1,
                "direction": "rx",
                "characteristic": "0000ff02-0000-1000-8000-00805f9b34fb",
                "data": "020452617942616e"
            },
        ]
    }
    
    filepath = "sample_capture.json"
    with open(filepath, 'w') as f:
        json.dump(sample_data, f, indent=2)
    
    print(f"📝 Created sample capture: {filepath}")
    return filepath


def main():
    parser = argparse.ArgumentParser(
        description="Analyze Bluetooth packets from Meta Ray-Ban glasses"
    )
    parser.add_argument(
        "input",
        type=str,
        nargs="?",
        help="Input JSON file with captured packets"
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Create and analyze a sample capture file"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        help="Output analysis results to JSON file"
    )

    args = parser.parse_args()

    analyzer = ProtocolAnalyzer()

    if args.sample:
        filepath = create_sample_capture()
        analyzer.load_json(filepath)
    elif args.input:
        analyzer.load_json(args.input)
    else:
        print("Usage: uv run src/analyzer.py <capture.json>")
        print("       uv run src/analyzer.py --sample")
        return

    analyzer.print_analysis()

    if args.output:
        results = {
            "structure": analyzer.analyze_structure(),
            "format_analysis": analyzer.guess_protocol_format(),
            "command_response_pairs": analyzer.find_command_response_pairs(),
        }
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n💾 Analysis saved to {args.output}")


if __name__ == "__main__":
    main()
