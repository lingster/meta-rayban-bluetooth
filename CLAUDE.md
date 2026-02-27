# Meta Ray-Ban Bluetooth Tools

## Project Overview

Tools for discovering, connecting to, and reverse engineering the Bluetooth protocol of Meta Ray-Ban smart glasses. Uses `bleak` (async BLE library) as the primary dependency.

## Package Management

- Uses **uv** as the package manager
- Python >= 3.12 required
- Run scripts with `uv run src/<script>.py`

## Documentation (docs/)

- `01-bluetooth-fundamentals.md` - Bluetooth protocol reference: Classic vs BLE, protocol stack, addressing, pairing/bonding, security modes, frequency hopping, and connection states.
- `02-bluetooth-discovery.md` - Device discovery mechanics: Classic inquiry process, BLE advertising/scanning, SDP, GATT discovery, AD types, and Python discovery examples using bleak.
- `03-meta-rayban-glasses.md` - Meta Ray-Ban specific info: hardware specs, expected BLE services/UUIDs, speculated command protocol (TLV format), Meta View app details, and reverse engineering approach.

## Source Files (src/)

- `compat.py` - Platform utilities: macOS detection, platform-aware address format hints, Classic BT gating
- `scanner.py` - BLE/Classic device discovery; filters by Meta company IDs (0x0397, 0x0157) and Ray-Ban name patterns
- `explorer.py` - GATT service/characteristic enumeration with optional notification subscription and characteristic writes
- `monitor.py` - Real-time BLE notification capture with optional interactive mode
- `analyzer.py` - Parses captured packet data to identify protocol patterns

## Key Constants

- Meta company IDs: `0x0397` (Meta Platforms), `0x0157` (Facebook legacy)
- Name patterns: "Ray-Ban", "Meta"
