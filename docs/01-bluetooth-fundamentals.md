# Bluetooth Fundamentals

## Overview

Bluetooth is a short-range wireless technology standard for exchanging data between fixed and mobile devices over short distances. It operates in the ISM band from 2.402 GHz to 2.48 GHz.

## Bluetooth Versions

| Version | Release | Key Features |
|---------|---------|--------------|
| 1.0 | 1999 | Initial release, 721 kbps |
| 2.0 + EDR | 2004 | Enhanced Data Rate (3 Mbps) |
| 3.0 + HS | 2009 | High Speed (24 Mbps via WiFi) |
| 4.0 | 2010 | Bluetooth Low Energy (BLE) |
| 4.2 | 2014 | Improved BLE, IoT features |
| 5.0 | 2016 | 2x speed, 4x range, 8x broadcast capacity |
| 5.1 | 2019 | Direction finding |
| 5.2 | 2020 | LE Audio, LC3 codec |
| 5.3 | 2021 | Improved reliability |
| 5.4 | 2023 | PAwR (Periodic Advertising with Responses) |

## Two Flavors: Classic vs BLE

### Bluetooth Classic (BR/EDR)

- **Use case**: Continuous, high-bandwidth streaming (audio, file transfer)
- **Power**: Higher power consumption
- **Data rate**: Up to 3 Mbps (EDR)
- **Range**: ~100m (Class 1), ~10m (Class 2)
- **Profiles**: A2DP, HFP, HSP, AVRCP, SPP, etc.

### Bluetooth Low Energy (BLE)

- **Use case**: Intermittent, low-bandwidth data (sensors, beacons, control)
- **Power**: Very low power consumption
- **Data rate**: 1-2 Mbps
- **Range**: ~100m
- **Protocol**: GATT (Generic Attribute Profile)

## Bluetooth Protocol Stack

```
┌─────────────────────────────────────────────────┐
│                 Applications                     │
├─────────────────────────────────────────────────┤
│     Profiles (A2DP, HFP, GATT, etc.)            │
├─────────────────────────────────────────────────┤
│   L2CAP (Logical Link Control & Adaptation)     │
├─────────────────────────────────────────────────┤
│        HCI (Host Controller Interface)          │
├─────────────────────────────────────────────────┤
│      Link Manager / Link Layer                  │
├─────────────────────────────────────────────────┤
│         Baseband / PHY Layer                    │
└─────────────────────────────────────────────────┘
```

## Addressing

### Bluetooth Device Address (BD_ADDR)

- 48-bit unique identifier (like MAC address)
- Format: `XX:XX:XX:XX:XX:XX`
- First 3 octets: OUI (Organizationally Unique Identifier)
- Last 3 octets: Device-specific

### Address Types (BLE)

| Type | Description |
|------|-------------|
| Public | Fixed, registered with IEEE |
| Random Static | Generated at boot, fixed until power cycle |
| Random Private Resolvable | Rotates, resolvable with IRK |
| Random Private Non-Resolvable | Rotates, not resolvable |

## Pairing & Bonding

### Pairing Methods

1. **Just Works**: No user interaction (least secure)
2. **Numeric Comparison**: Confirm 6-digit code on both devices
3. **Passkey Entry**: Enter PIN on one/both devices
4. **Out of Band (OOB)**: Use NFC or other channel

### Bonding

- Stores pairing information (keys) for future connections
- Link Key (Classic) or Long Term Key (BLE)
- Enables reconnection without re-pairing

## Security

### Encryption

- AES-128-CCM encryption
- Link encryption after pairing
- Key exchange via ECDH (Secure Connections)

### Security Modes

**Classic:**
- Mode 1: No security
- Mode 2: Service-level security
- Mode 3: Link-level security
- Mode 4: SSP (Secure Simple Pairing)

**BLE:**
- Mode 1: No security / Encryption
- Mode 2: Data signing

## Power Classes

| Class | Max Power | Range |
|-------|-----------|-------|
| 1 | 100 mW (20 dBm) | ~100m |
| 2 | 2.5 mW (4 dBm) | ~10m |
| 3 | 1 mW (0 dBm) | ~1m |

## Frequency Hopping

- Bluetooth uses FHSS (Frequency Hopping Spread Spectrum)
- 79 channels (Classic) or 40 channels (BLE)
- Hops 1600 times/second (Classic)
- Provides resilience against interference

## Connection States

```
┌──────────────┐
│   Standby    │◄─────────────────┐
└──────┬───────┘                  │
       │ Advertise/Scan           │
       ▼                          │
┌──────────────┐                  │
│  Advertising │                  │
│  / Scanning  │                  │
└──────┬───────┘                  │
       │ Connect                  │
       ▼                          │
┌──────────────┐                  │
│  Initiating  │                  │
└──────┬───────┘                  │
       │ Connected                │ Disconnect
       ▼                          │
┌──────────────┐                  │
│  Connected   │──────────────────┘
└──────────────┘
```
