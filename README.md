# Meta Ray-Ban Bluetooth Tools

Tools for discovering, connecting to, and reverse engineering the Bluetooth protocol of Meta Ray-Ban smart glasses.

> ⚠️ **Disclaimer**: This project is for educational and research purposes only. Use responsibly and in compliance with applicable laws.

## Features

- 🔍 **Scanner**: Find Meta Ray-Ban glasses via BLE and Classic Bluetooth
- 🔗 **Explorer**: Connect and enumerate all GATT services/characteristics
- 📡 **Monitor**: Real-time notification capture with logging
- 📊 **Analyzer**: Parse captured packets to identify protocol patterns

## Documentation

- [Bluetooth Fundamentals](docs/01-bluetooth-fundamentals.md) - Overview of Bluetooth technology
- [Bluetooth Discovery](docs/02-bluetooth-discovery.md) - How device discovery works
- [Meta Ray-Ban Glasses](docs/03-meta-rayban-glasses.md) - Device-specific information

## Installation

```bash
# Clone the repository
git clone https://github.com/lingster/meta-rayban-bluetooth.git
cd meta-rayban-bluetooth

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

### Linux Setup

```bash
# Install BlueZ and dependencies
sudo apt install bluetooth bluez python3-dev libbluetooth-dev

# Ensure Bluetooth is enabled
sudo systemctl start bluetooth
sudo hciconfig hci0 up

# Run without sudo (add user to bluetooth group)
sudo usermod -aG bluetooth $USER
# Log out and back in
```

## Usage

### 1. Scan for Devices

```bash
# Basic scan (30 seconds)
python src/scanner.py

# Extended scan with verbose output
python src/scanner.py -d 60 -v

# Include Classic Bluetooth (requires pybluez)
python src/scanner.py --classic

# Save results to file
python src/scanner.py -o scan_results.json
```

### 2. Explore GATT Services

```bash
# Connect and enumerate services
python src/explorer.py AA:BB:CC:DD:EE:FF

# Verbose output (include descriptors)
python src/explorer.py AA:BB:CC:DD:EE:FF -v

# Subscribe to notifications for 60 seconds
python src/explorer.py AA:BB:CC:DD:EE:FF -n 60

# Save device profile
python src/explorer.py AA:BB:CC:DD:EE:FF -o profile.json

# Write to a characteristic
python src/explorer.py AA:BB:CC:DD:EE:FF -w <uuid> <hex_data>
```

### 3. Monitor Traffic

```bash
# Monitor notifications (save to capture.json)
python src/monitor.py AA:BB:CC:DD:EE:FF

# Monitor for 5 minutes
python src/monitor.py AA:BB:CC:DD:EE:FF -d 300

# Interactive mode (send commands)
python src/monitor.py AA:BB:CC:DD:EE:FF -i
```

### 4. Analyze Captured Data

```bash
# Analyze a capture file
python src/analyzer.py capture.json

# Create and analyze sample data
python src/analyzer.py --sample

# Save analysis to file
python src/analyzer.py capture.json -o analysis.json
```

## Project Structure

```
meta-rayban-bluetooth/
├── docs/
│   ├── 01-bluetooth-fundamentals.md
│   ├── 02-bluetooth-discovery.md
│   └── 03-meta-rayban-glasses.md
├── src/
│   ├── scanner.py      # Device discovery
│   ├── explorer.py     # GATT enumeration
│   ├── monitor.py      # Real-time capture
│   └── analyzer.py     # Packet analysis
├── tools/              # Additional utilities
├── requirements.txt
└── README.md
```

## Reverse Engineering Workflow

1. **Discovery**: Use `scanner.py` to find your glasses
2. **Enumeration**: Use `explorer.py` to map all services
3. **Capture**: Use `monitor.py` while using the official app
4. **Analysis**: Use `analyzer.py` to identify patterns
5. **Document**: Update `docs/03-meta-rayban-glasses.md` with findings

### Tips

- Capture traffic while performing specific actions in the Meta View app
- Compare packets before and after actions to identify command bytes
- Look for consistent prefixes that might be command IDs
- Monitor battery level characteristic for validation

## Known Services (To Be Documented)

| UUID | Description | Notes |
|------|-------------|-------|
| 0x180A | Device Information | Standard |
| 0x180F | Battery Service | Standard |
| TBD | Camera Control | Proprietary |
| TBD | Voice Assistant | Proprietary |

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Document any discovered UUIDs or protocols
4. Submit a pull request

## Legal

- This project is for educational purposes only
- Reverse engineering for interoperability may be legal in your jurisdiction
- Do not distribute proprietary code or circumvent copy protection
- The Meta Ray-Ban trademark belongs to Meta Platforms, Inc.

## License

MIT License - See LICENSE file for details.
