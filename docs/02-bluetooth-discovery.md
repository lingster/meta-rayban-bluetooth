# Bluetooth Discovery

## Overview

Device discovery is how Bluetooth devices find and identify each other. The process differs significantly between Classic Bluetooth and BLE.

## Classic Bluetooth Discovery

### Inquiry Process

```
┌─────────────────┐                    ┌─────────────────┐
│   Discovering   │                    │  Discoverable   │
│     Device      │                    │     Device      │
└────────┬────────┘                    └────────┬────────┘
         │                                      │
         │  ───── Inquiry (IAC) ─────►          │
         │                                      │
         │  ◄──── FHS Packet ─────────          │
         │       (BD_ADDR, Clock)               │
         │                                      │
         │  ───── Inquiry (IAC) ─────►          │
         │                                      │
         │  ◄──── EIR (Extended) ─────          │
         │       (Name, Services, etc.)         │
         ▼                                      ▼
```

### Inquiry Access Codes (IAC)

| Code | Name | Use |
|------|------|-----|
| GIAC | General IAC | Discover all devices |
| LIAC | Limited IAC | Discover devices in limited mode |
| DIAC | Dedicated IAC | Device-specific discovery |

### Extended Inquiry Response (EIR)

EIR packets contain additional information:

- Complete/Shortened Local Name
- Complete/Incomplete List of UUIDs
- TX Power Level
- Class of Device
- Manufacturer Specific Data

### Class of Device (CoD)

24-bit field describing device type:

```
┌────────────────┬────────────────┬──────────────┐
│ Major Service  │ Major Device   │ Minor Device │
│ Class (11 bit) │ Class (5 bit)  │ Class (6 bit)│
└────────────────┴────────────────┴──────────────┘
```

**Major Device Classes:**
- 0x01: Computer
- 0x02: Phone
- 0x03: LAN/Network Access
- 0x04: Audio/Video
- 0x05: Peripheral
- 0x06: Imaging
- 0x07: Wearable
- 0x08: Toy

**Example (Headphones):**
- Major: 0x04 (Audio/Video)
- Minor: 0x01 (Headset)
- CoD: `0x240404`

## BLE Discovery (Advertising & Scanning)

### Advertising

BLE devices broadcast advertisement packets on 3 dedicated channels (37, 38, 39).

```
┌─────────────────────────────────────────────────────────┐
│                  Advertisement Packet                    │
├─────────────────┬────────────────┬──────────────────────┤
│ Preamble (1B)   │ Access Addr(4B)│ PDU (2-257B)         │
├─────────────────┴────────────────┼──────────────────────┤
│ CRC (3B)                         │                      │
└──────────────────────────────────┴──────────────────────┘
```

### Advertising Types

| Type | Name | Connectable | Scannable |
|------|------|-------------|-----------|
| ADV_IND | Connectable Undirected | Yes | Yes |
| ADV_DIRECT_IND | Connectable Directed | Yes | No |
| ADV_SCAN_IND | Scannable Undirected | No | Yes |
| ADV_NONCONN_IND | Non-connectable | No | No |
| ADV_EXT_IND | Extended (BT 5.0+) | Varies | Varies |

### Advertising Data (AD) Structure

```
┌─────────┬──────┬─────────────────────────────────────┐
│ Length  │ Type │            Data                     │
│ (1 byte)│(1 B) │       (Length-1 bytes)              │
└─────────┴──────┴─────────────────────────────────────┘
```

### Common AD Types

| Type | Name | Description |
|------|------|-------------|
| 0x01 | Flags | Discoverability & BR/EDR support |
| 0x02 | Incomplete 16-bit UUIDs | Partial service list |
| 0x03 | Complete 16-bit UUIDs | Full service list |
| 0x06 | Incomplete 128-bit UUIDs | Partial custom services |
| 0x07 | Complete 128-bit UUIDs | Full custom services |
| 0x08 | Shortened Local Name | Truncated device name |
| 0x09 | Complete Local Name | Full device name |
| 0x0A | TX Power Level | Transmit power |
| 0xFF | Manufacturer Specific | Vendor data |

### Flags Byte

```
Bit 0: LE Limited Discoverable Mode
Bit 1: LE General Discoverable Mode
Bit 2: BR/EDR Not Supported
Bit 3: LE + BR/EDR (Controller)
Bit 4: LE + BR/EDR (Host)
```

### Scanning

Two types of scanning:

**Passive Scanning:**
- Only listens for advertisements
- No packets sent
- Lower power

**Active Scanning:**
```
┌──────────┐                         ┌────────────┐
│ Scanner  │                         │ Advertiser │
└────┬─────┘                         └─────┬──────┘
     │                                     │
     │   ◄──── ADV_IND ─────────────       │
     │                                     │
     │   ───── SCAN_REQ ──────────►        │
     │                                     │
     │   ◄──── SCAN_RSP ───────────        │
     │       (Additional data)             │
     ▼                                     ▼
```

### Scan Response

- Up to 31 additional bytes
- Only sent in response to SCAN_REQ
- Contains data that didn't fit in advertisement

## Service Discovery Protocol (SDP)

### Classic Bluetooth

After connection, use SDP to discover services:

```
┌─────────┐                              ┌─────────┐
│ Client  │                              │ Server  │
└────┬────┘                              └────┬────┘
     │                                        │
     │ ─── ServiceSearchRequest ────►         │
     │                                        │
     │ ◄── ServiceSearchResponse ────         │
     │     (Service Record Handles)           │
     │                                        │
     │ ─── ServiceAttributeRequest ──►        │
     │                                        │
     │ ◄── ServiceAttributeResponse ──        │
     │     (Service Attributes)               │
     ▼                                        ▼
```

### BLE (GATT Discovery)

BLE uses GATT for service discovery:

```python
# Hierarchy
Profile
└── Service (UUID)
    ├── Characteristic (UUID)
    │   ├── Value
    │   └── Descriptor(s)
    └── Characteristic (UUID)
        ├── Value
        └── Descriptor(s)
```

## Practical Discovery in Python

### Using BlueZ (Linux)

```bash
# Install dependencies
sudo apt install bluetooth bluez python3-dbus

# Enable Bluetooth
sudo systemctl start bluetooth
sudo hciconfig hci0 up
```

### Python Libraries

| Library | Type | Platform |
|---------|------|----------|
| `pybluez` | Classic + limited BLE | Linux, Windows |
| `bleak` | BLE (async) | Cross-platform |
| `bluepy` | BLE | Linux only |
| `dbus-python` | BlueZ D-Bus | Linux only |

### Discovery Code Example

```python
import asyncio
from bleak import BleakScanner

async def discover():
    devices = await BleakScanner.discover(timeout=10.0)
    for device in devices:
        print(f"{device.address}: {device.name}")
        print(f"  RSSI: {device.rssi} dBm")
        if device.metadata.get("manufacturer_data"):
            for company_id, data in device.metadata["manufacturer_data"].items():
                print(f"  Manufacturer ({company_id}): {data.hex()}")

asyncio.run(discover())
```

## Filtering & Identifying Devices

### By Name Pattern
```python
# Ray-Ban Meta glasses advertise as "RB Meta <model>" (e.g. "RB Meta 005G")
PATTERNS = ["ray-ban", "rayban", "rb meta", "meta", "stories"]
devices = [d for d in all_devices
           if d.name and any(p in d.name.lower() for p in PATTERNS)]
```

### By Manufacturer ID
```python
# Known Meta/Facebook company IDs
META_COMPANY_IDS = {
    0x0397,  # Meta Platforms, Inc.
    0x0157,  # Facebook, Inc. (older)
    0x01AB,  # Meta Platforms (observed on Ray-Ban Meta glasses)
}

devices = [d for d in all_devices
           if META_COMPANY_IDS & set(d.metadata.get("manufacturer_data", {}).keys())]
```

### By Service UUID
```python
# Filter by specific service
TARGET_SERVICE = "0000180d-0000-1000-8000-00805f9b34fb"  # Heart Rate

devices = [d for d in all_devices 
           if TARGET_SERVICE in d.metadata.get("uuids", [])]
```

## Security Considerations

### Discovery Attacks

1. **Bluejacking**: Sending unsolicited messages
2. **Bluesnarfing**: Unauthorized data access
3. **Bluebugging**: Taking control of device
4. **KNOB Attack**: Key negotiation weakness
5. **BIAS Attack**: Impersonation via role switch

### Mitigations

- Keep devices non-discoverable when not pairing
- Use Secure Connections (ECDH)
- Require user confirmation for pairing
- Rotate BLE addresses (RPA)
- Limit inquiry/advertising duration
