# Rocket Motor Test Stand

A complete rocket motor thrust measurement system with real-time data streaming, web-based visualization, and comprehensive analysis.

## System Architecture

```
ESP32-C3 + HX711 + Load Cell
         |
         | (WiFi WebSocket)
         v
  Flask Server (Laptop)
         |
         | (WebSocket)
         v
  Web Dashboard (Browser)
```

## Hardware Requirements

- **Microcontroller**: ESP32-C3 development board
- **Load Cell Amplifier**: HX711
- **Load Cell**: Beam type, 5-50kg range recommended
- **Power**: USB for ESP32 (battery-powered during tests)
- **Computer**: Laptop/PC running Flask server

### Hardware Connections

```
Load Cell <-> HX711 <-> ESP32-C3

Load Cell (4-wire):
  RED    -> E+ (Excitation+)
  BLACK  -> E- (Excitation-)
  WHITE  -> A+ (Signal+)
  GREEN  -> A- (Signal-)

HX711 <-> ESP32-C3:
  VCC -> 3.3V
  GND -> GND
  DT  -> GPIO 2
  SCK -> GPIO 3
```

## Software Stack

### ESP32 Firmware
- **Platform**: PlatformIO with Arduino framework
- **Libraries**: HX711 (bogde), ArduinoWebsockets, ArduinoJson
- **Features**: 80Hz sampling, WiFi streaming, persistent calibration

### Backend Server
- **Framework**: Flask with Flask-SocketIO
- **Analysis**: NumPy, SciPy for signal processing
- **Storage**: SQLite database for test history

### Frontend Dashboard
- **UI**: HTML5, CSS3, JavaScript
- **Plotting**: Chart.js with real-time streaming
- **Features**: Live visualization, analysis display, test history

## Installation

### 1. Clone Repository

```bash
cd /home/fred/roccet_test_stand
```

### 2. Backend Setup

```bash
cd server

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Firmware Setup

```bash
cd firmware

# Install PlatformIO (if not already installed)
pip install platformio

# Copy config template
cp src/config.h.example src/config.h

# Edit config.h with your settings
nano src/config.h
```

**Edit `firmware/src/config.h`:**
- Set `WIFI_SSID` to your WiFi network name
- Set `WIFI_PASSWORD` to your WiFi password
- Set `SERVER_HOST` to your laptop's IP address (find with `ip addr` or `ifconfig`)

Example:
```cpp
#define WIFI_SSID "MyNetwork"
#define WIFI_PASSWORD "MyPassword123"
#define SERVER_HOST "192.168.1.100"  // Your laptop IP
```

### 4. Flash ESP32 Firmware

```bash
cd firmware

# Build and upload
pio run --target upload

# Monitor serial output
pio device monitor
```

## Usage

### 1. Start Flask Server

```bash
cd server
source venv/bin/activate  # If using virtual environment
python app.py
```

The server will start on `http://0.0.0.0:5000`

You should see:
```
============================================================
Rocket Motor Test Stand Server
============================================================
Database: ../data/tests.db
Server starting on http://0.0.0.0:5000
ESP32 WebSocket: ws://[server-ip]:5000/esp32
Dashboard WebSocket: ws://[server-ip]:5000/dashboard
============================================================
```

### 2. Power On ESP32

Connect ESP32 via USB. Monitor serial output to verify connection:

```
=================================
Rocket Motor Test Stand - ESP32
=================================

Initializing HX711...
HX711 initialized successfully
Loading calibration from NVS...
Connecting to WiFi: MyNetwork
...
WiFi connected!
IP Address: 192.168.1.42
Connecting to WebSocket server: 192.168.1.100:5000
WebSocket connected!
Setup complete. Ready to stream data.
```

### 3. Open Web Dashboard

Open browser and navigate to:
```
http://localhost:5000
```

Or from another device on the same network:
```
http://[server-ip]:5000
```

### 4. Calibrate Load Cell

**First time setup requires calibration:**

1. **Tare**: Remove all weight from load cell, click "Tare" button
2. **Calibrate**: Place a known mass on load cell (e.g., 500g weight)
3. Click "Calibrate", enter the known mass in grams
4. ESP32 will calculate and save calibration factor

### 5. Run a Test

1. Mount rocket motor on test stand
2. Click "Start Test" when ready
3. Ignite motor (safely!)
4. Watch real-time thrust curve
5. Click "Stop Test" when complete
6. View comprehensive analysis

## Features

### Real-Time Monitoring
- Live thrust curve plotting (80 Hz sample rate)
- Current, peak, and duration indicators
- Rolling 30-second window display

### Comprehensive Analysis (15+ Metrics)

**Core Metrics:**
- Peak thrust (N)
- Average thrust (N)
- Total impulse (N·s)
- Burn time (s)
- Motor class (A through K+)

**Advanced Metrics:**
- Time to peak thrust
- Rise rate and decay rate (N/s)
- Thrust stability (standard deviation)
- Impulse efficiency
- Burn profile classification (progressive/neutral/regressive)
- CATO detection (catastrophic failure)
- Specific impulse (if propellant mass provided)

### Data Management
- SQLite database for test history
- CSV export for data analysis
- Test comparison and overlay
- Downloadable reports

## Troubleshooting

### ESP32 Won't Connect to WiFi

- Verify SSID and password in `firmware/src/config.h`
- Check WiFi signal strength
- Ensure 2.4GHz network (ESP32-C3 doesn't support 5GHz)
- Monitor serial output for error messages

### WebSocket Connection Failed

- Verify server IP address in `config.h`
- Check firewall settings (allow port 5000)
- Ensure ESP32 and server are on same network
- Try pinging server from another device

### HX711 Not Ready

- Check wiring connections (DT and SCK pins)
- Verify load cell is properly connected to HX711
- Check power supply (3.3V to HX711)
- Try different GPIO pins if needed

### Inaccurate Readings

- Perform calibration procedure
- Check for loose connections
- Ensure load cell is rigidly mounted
- Minimize vibration and electromagnetic interference
- Verify load cell capacity matches thrust levels

### Analysis Seems Wrong

- Ensure proper baseline (tare before test)
- Check for data gaps (WiFi dropouts)
- Verify sample rate is consistent
- Review raw data in CSV export

## Testing Without Hardware

Use the simulator to test the system:

```bash
cd tests

# Install additional dependency
pip install websocket-client matplotlib

# Run simulator
python simulator.py
```

Or stream simulated data to server:

```python
from simulator import WebSocketSimulator

sim = WebSocketSimulator('ws://localhost:5000/esp32')
sim.stream_test(peak_thrust=50.0, burn_time=2.0, profile='neutral')
```

## Running Unit Tests

```bash
cd tests
pytest test_analysis.py -v
```

Expected output:
```
test_analysis.py::TestThrustAnalyzer::test_rectangular_impulse PASSED
test_analysis.py::TestThrustAnalyzer::test_triangular_impulse PASSED
test_analysis.py::TestThrustAnalyzer::test_peak_thrust PASSED
...
```

## Project Structure

```
roccet_test_stand/
├── firmware/              # ESP32-C3 firmware
│   ├── platformio.ini     # PlatformIO configuration
│   └── src/
│       ├── main.cpp       # Main firmware code
│       ├── config.h       # WiFi and pin configuration
│       └── config.h.example
├── server/                # Flask backend
│   ├── app.py            # Main Flask application
│   ├── websocket_handler.py  # WebSocket communication
│   ├── analysis.py       # Thrust curve analysis
│   ├── models.py         # Database models
│   ├── config.py         # Server configuration
│   ├── requirements.txt  # Python dependencies
│   └── static/           # Web dashboard
│       ├── index.html
│       ├── css/styles.css
│       └── js/
│           ├── app.js
│           └── charts.js
├── data/                 # Data storage
│   ├── tests.db         # SQLite database
│   └── tests/           # CSV exports
├── tests/               # Testing utilities
│   ├── test_analysis.py  # Unit tests
│   └── simulator.py      # Test data generator
└── README.md
```

## Configuration

### Server Configuration

Edit `server/config.py` to customize:

```python
# Analysis parameters
BURN_THRESHOLD = 0.05      # 5% of peak defines burn
SMOOTHING_WINDOW = 11      # Savitzky-Golay window
BASELINE_DURATION = 0.5    # Seconds for baseline averaging

# Sampling
EXPECTED_SAMPLE_RATE = 80  # Hz
```

### Firmware Configuration

Edit `firmware/src/config.h`:

```cpp
#define SAMPLE_RATE_HZ 80  # Sampling frequency
#define USE_STATUS_LED true  # Enable LED indicator
#define STATUS_LED_PIN 8    # GPIO for status LED
```

## Safety Guidelines

### Electrical Safety
- Keep electronics away from ignition system
- Use optical isolation if needed
- Ground all metal structures
- Use battery power during test (disconnect USB)

### Test Stand Safety
- Rigidly mount test stand
- Use blast shield
- Clear area of flammable materials
- Have fire extinguisher ready
- Never approach motor during or immediately after burn

### Operational Safety
- Test in open area or test cell
- Follow local regulations
- Maintain safe distance during ignition
- Allow cooldown period before handling

## Motor Classification Reference

Based on total impulse (N·s):

| Class | Total Impulse (N·s) | Example Motors |
|-------|---------------------|----------------|
| A     | 1.26 - 2.5          | Estes A8       |
| B     | 2.5 - 5             | Estes B6       |
| C     | 5 - 10              | Estes C6       |
| D     | 10 - 20             | Estes D12      |
| E     | 20 - 40             | Aerotech E30   |
| F     | 40 - 80             | Aerotech F39   |
| G     | 80 - 160            | Cesaroni G80   |
| H     | 160 - 320           | Cesaroni H268  |
| I     | 320 - 640           | Loki I285      |
| J+    | > 640               | High power     |

## Future Enhancements

- [ ] Multi-motor comparison overlays
- [ ] Automated report generation (PDF)
- [ ] Temperature monitoring
- [ ] Pressure sensing
- [ ] Video synchronization
- [ ] Cloud data backup
- [ ] Mobile app
- [ ] Hardware emergency stop
- [ ] Multi-user authentication

## Contributing

This is a personal project, but suggestions and improvements are welcome!

## License

MIT License - Feel free to use and modify for your projects.

## Acknowledgments

- HX711 library by bogde
- Flask-SocketIO by Miguel Grinberg
- Chart.js community
- Rocket motor community for testing insights

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review serial monitor output
3. Check browser console for errors
4. Verify all connections and configuration

## Version History

- **v1.0** (2026-01-25): Initial release
  - ESP32-C3 firmware with HX711 integration
  - Flask backend with WebSocket streaming
  - Real-time web dashboard
  - 15+ analysis metrics
  - SQLite data storage
  - Calibration system

---

**Happy Testing! 🚀**
