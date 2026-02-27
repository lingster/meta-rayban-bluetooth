# Meta Ray-Ban Smart Glasses

## Overview

Meta Ray-Ban smart glasses (formerly Facebook Ray-Ban Stories) are smart glasses developed by Meta in partnership with EssilorLuxottica. They feature cameras, speakers, microphones, and Bluetooth connectivity.

## Hardware Specifications

### Audio
- Open-ear speakers with directional audio
- 5 microphones for voice capture and beamforming
- Qualcomm Snapdragon AR1 Gen 1 platform (2nd gen)

### Camera
- Dual 12MP cameras (2nd gen) / 5MP (1st gen)
- LED indicator when recording
- Up to 1080p video recording

### Connectivity
- Bluetooth 5.2 (Classic + BLE)
- WiFi for large file transfers
- USB-C charging case

### Battery
- ~4 hours continuous use
- Charging case provides additional charges

## Bluetooth Profiles

### Audio Profiles (Classic Bluetooth)

| Profile | Purpose |
|---------|---------|
| A2DP (Advanced Audio Distribution) | High-quality audio streaming |
| AVRCP (Audio/Video Remote Control) | Media playback control |
| HFP (Hands-Free Profile) | Phone calls |
| HSP (Headset Profile) | Basic telephony |

### BLE Services

The glasses likely implement:

| Service | UUID | Purpose |
|---------|------|---------|
| Generic Access | 0x1800 | Device name, appearance |
| Generic Attribute | 0x1801 | Service changed |
| Device Information | 0x180A | Manufacturer, model, firmware |
| Battery Service | 0x180F | Battery level |
| Proprietary | Custom 128-bit | Meta-specific features |

## Enabling Bluetooth Pairing Mode

To make the glasses discoverable for BLE scanning:

1. Place the glasses in the charging case
2. Press and hold the button on the back of the case for 5 seconds
3. Wait until the LED light on the case turns blue
4. The glasses are now in pairing/discoverable mode

## Device Identification

### Bluetooth Name Patterns
- "Ray-Ban Stories" (1st gen)
- "Ray-Ban | Meta" (2nd gen)
- **"RB Meta 005G"** (observed, 2nd gen — model suffix varies)

### Manufacturer Data
- Company ID: **`0x01AB`** (observed on Ray-Ban Meta glasses)
- Company ID: `0x0397` (Meta Platforms, Inc. — registered)
- Company ID: `0x0157` (Facebook, Inc. — legacy)
- Example payload: `020103b2c5fc1d08bb01` (10 bytes)

### Advertised Service UUIDs
- **`0000fd5f-0000-1000-8000-00805f9b34fb`** (observed during BLE advertising)

### Addressing on macOS
On macOS, CoreBluetooth does not expose hardware MAC addresses. Instead, devices are identified by CoreBluetooth UUIDs (e.g. `3B07C626-8BC4-0545-9F27-93137792C31A`). These UUIDs are stable per-device on a given Mac but differ across machines.

## Expected GATT Services

Based on similar devices, the glasses likely expose:

### Standard Services

```
Service: Device Information (0x180A)
├── Manufacturer Name String (0x2A29)
├── Model Number String (0x2A24)
├── Serial Number String (0x2A25)
├── Hardware Revision String (0x2A27)
├── Firmware Revision String (0x2A26)
└── Software Revision String (0x2A28)

Service: Battery Service (0x180F)
├── Battery Level (0x2A19)
└── Battery Level Status (if extended)
```

### Proprietary Services

Custom services for:
- Camera control (capture photo/video)
- Voice assistant activation
- Firmware updates (OTA)
- Configuration settings
- Notification handling
- Status reporting

## Communication Protocol (Speculation)

### Command Structure

Likely uses a TLV (Type-Length-Value) or similar format:

```
┌────────────┬────────────┬───────────────────┐
│ Command ID │   Length   │      Payload      │
│  (1-2 B)   │  (1-2 B)   │   (Variable)      │
└────────────┴────────────┴───────────────────┘
```

### Possible Commands

| Command | Description |
|---------|-------------|
| 0x01 | Get device status |
| 0x02 | Get battery level |
| 0x10 | Capture photo |
| 0x11 | Start video |
| 0x12 | Stop video |
| 0x20 | Voice assistant trigger |
| 0x30 | Get settings |
| 0x31 | Set settings |
| 0xF0+ | Firmware update |

## Official App

### Meta View App
- iOS and Android
- Required for initial setup
- Manages media transfer
- Firmware updates
- Settings configuration

### App Communication
- Uses both Bluetooth and WiFi
- Bluetooth for control and notifications
- WiFi for media transfer (faster)

## Reverse Engineering Approach

### 1. Passive Discovery
```bash
# Scan for the glasses (using this project's scanner)
uv run src/scanner.py -d 20 -v

# Or using system tools (Linux)
sudo hcitool lescan
sudo bluetoothctl scan on
```

### 2. Capture Pairing
- Use Wireshark with Bluetooth adapter
- Capture HCI traffic during pairing

### 3. Service Enumeration
```python
# Use bleak to discover services
async with BleakClient(address) as client:
    for service in client.services:
        print(f"Service: {service.uuid}")
        for char in service.characteristics:
            print(f"  Char: {char.uuid} [{char.properties}]")
```

### 4. Traffic Analysis
- Capture Bluetooth traffic
- Analyze with Wireshark
- Look for patterns in GATT writes/notifications

### 5. App Analysis
- Decompile Meta View APK
- Look for Bluetooth UUIDs
- Find command definitions

## Discovered UUIDs

| UUID | Description | Source |
|------|-------------|--------|
| `0000fd5f-0000-1000-8000-00805f9b34fb` | Advertised service (purpose TBD) | BLE advertising |
| TBD | Control service | Not yet discovered |
| TBD | Status notifications | Not yet discovered |
| TBD | Camera control | Not yet discovered |
| TBD | Audio settings | Not yet discovered |

## Security Notes

### Pairing
- Likely requires Numeric Comparison
- May require app confirmation
- Bonding stores keys for reconnection

### Encryption
- All communication should be encrypted
- AES-128-CCM after pairing

### Privacy
- Camera LED cannot be disabled (by design)
- Voice activation requires wake word

## Legal Considerations

⚠️ **Important**: Reverse engineering for interoperability may be legal in many jurisdictions, but:
- Don't distribute proprietary code
- Don't circumvent copy protection
- Check local laws (DMCA, EU directives)
- This is for personal research/learning only
