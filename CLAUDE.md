# Meta Ray-Ban Bluetooth Tools

## Coding standards
Use SOLID and DRY coding principals
make use of python + typer to create cli utils

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
- `04-audio-retrieval.md` - Audio retrieval findings: DAT SDK analysis (audio not yet public), VisionClaw audio pipeline (16kHz PCM via system APIs), comparison of approaches, and recommendations for Python-based capture.

## Source Files (src/)

- `compat.py` - Platform utilities: macOS detection, platform-aware address format hints, Classic BT gating
- `scanner.py` - BLE/Classic device discovery; filters by Meta company IDs (0x0397, 0x0157) and Ray-Ban name patterns
- `explorer.py` - GATT service/characteristic enumeration with optional notification subscription and characteristic writes
- `monitor.py` - Real-time BLE notification capture with optional interactive mode
- `analyzer.py` - Parses captured packet data to identify protocol patterns
- `recorder.py` - Audio capture from glasses microphone (paired via macOS Classic BT) with MP3 encoding; uses typer CLI
- `audio_sniff.py` - Audio protocol reverse-engineering: passive BLE ad monitoring, notification sniffing, and HCI capture guide; uses typer CLI

## Key Constants

- Meta company IDs: `0x01AB` (observed on Ray-Ban Meta), `0x0397` (Meta Platforms), `0x0157` (Facebook legacy)
- Name patterns: "Ray-Ban", "RB Meta", "Meta", "Stories"
- Advertised service UUID: `0000fd5f-0000-1000-8000-00805f9b34fb`
- Observed device name: "RB Meta 005G"
- Observed manufacturer data: `020103b2c5fc1d08bb01` (10 bytes, company `0x01AB`)
