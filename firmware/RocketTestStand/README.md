# Rocket Test Stand - Arduino IDE Version

This is the Arduino IDE version of the firmware. It's a single `.ino` file that's easier to use than the PlatformIO version.

## Required Libraries

Install these via Arduino IDE Library Manager (**Tools → Manage Libraries**):

1. **HX711** by Bogdan Necula (bogde) - v0.7.5 or newer
2. **ArduinoWebsockets** by Gil Maimon - v0.5.3 or newer
3. **ArduinoJson** by Benoit Blanchon - v6.21.3 or newer (version 6.x)

## ESP32 Board Support

If not already installed:

1. **File → Preferences**
2. Add to "Additional Board Manager URLs":
   ```
   https://espressif.github.io/arduino-esp32/package_esp32_index.json
   ```
3. **Tools → Board → Boards Manager**
4. Search for `esp32` and install **esp32 by Espressif Systems**

## Board Configuration

Select:
- **Board**: ESP32C3 Dev Module
- **Upload Speed**: 921600
- **USB CDC On Boot**: Enabled
- **CPU Frequency**: 160MHz (WiFi)
- **Flash Size**: 4MB
- **Partition Scheme**: Default 4MB with spiffs

## Configuration

Edit these lines in `RocketTestStand.ino`:

```cpp
// WiFi credentials
#define WIFI_SSID "Home"           // Your WiFi network name
#define WIFI_PASSWORD "Airport25"   // Your WiFi password

// Server connection
#define SERVER_HOST "deb.local"     // Server hostname or IP
#define SERVER_PORT 5000

// HX711 pins
#define HX711_DOUT_PIN 4  // DT pin
#define HX711_SCK_PIN 3   // SCK pin
```

## Hardware Connections

```
HX711 → ESP32-C3
DT    → GPIO 4
SCK   → GPIO 3
VCC   → 3.3V
GND   → GND
```

## Upload & Monitor

1. Open `RocketTestStand.ino` in Arduino IDE
2. Select correct board and port
3. Click **Upload** (→)
4. Open **Serial Monitor** (115200 baud)
5. Press **RESET** on ESP32 to see boot messages

## Expected Output

```
=================================
Rocket Motor Test Stand - ESP32
=================================

Initializing HX711...
Pins - DOUT: 4, SCK: 3
HX711 initialized successfully
Loading calibration from NVS...
Loaded scale: 1.000000
Loaded offset: 0
Connecting to WiFi: Home
....
WiFi connected!
IP Address: 192.168.50.xxx
Connecting to WebSocket server: deb.local:5000
WebSocket connected!

Setup complete. Ready to stream data.

Raw: 8388608, Mass: 0.00g, Force: 0.00N
...
```

## Troubleshooting

### "HX711 not found"
- Check wiring (DT → GPIO 4, SCK → GPIO 3)
- Verify power (3.3V, GND)
- Try different pins

### "WiFi connection failed"
- Check SSID and password
- Ensure 2.4GHz network (ESP32 doesn't support 5GHz)
- Check signal strength

### "WebSocket connection failed"
- Verify server is running: `python server/app.py`
- Check SERVER_HOST (try IP instead of hostname)
- Ping the server: `ping deb.local`

### Serial monitor shows nothing
- Check baud rate is 115200
- Press RESET button on ESP32
- Try different USB cable/port

## Calibration

1. **Tare**: Remove all weight, click "Tare" in dashboard
2. **Calibrate**: Place known weight (e.g., 500g), enter mass, click "Calibrate"
3. Calibration is saved to ESP32's NVS (survives reboot)

## Debug Output

To reduce serial output, comment out this line:

```cpp
// Serial.printf("Raw: %ld, Mass: %.2fg, Force: %.2fN\n", raw_value, mass_grams, force_n);
```

## Differences from PlatformIO Version

- Single file (no separate config.h)
- All configuration at top of file
- Same functionality
- Easier to modify and upload
