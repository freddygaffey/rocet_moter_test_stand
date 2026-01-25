/**
 * Rocket Motor Test Stand - ESP32-C3 Firmware
 *
 * Arduino IDE Version
 *
 * Hardware:
 * - ESP32-C3
 * - HX711 Load Cell Amplifier
 * - Load Cell
 *
 * Connections:
 * - HX711 DT  -> GPIO 4
 * - HX711 SCK -> GPIO 3
 * - HX711 VCC -> 3.3V
 * - HX711 GND -> GND
 *
 * Required Libraries (install via Library Manager):
 * - HX711 by Bogdan Necula (bogde)
 * - ArduinoWebsockets by Gil Maimon
 * - ArduinoJson by Benoit Blanchon
 */

#include <WiFi.h>
#include <ArduinoWebsockets.h>
#include <ArduinoJson.h>
#include <HX711.h>
#include <Preferences.h>

using namespace websockets;

// ============================================
// CONFIGURATION - Edit these for your setup
// ============================================

// WiFi credentials
#define WIFI_SSID "Home"
#define WIFI_PASSWORD "Airport25"

// Server connection
#define SERVER_HOST "deb.local"  // Or use IP like "192.168.50.132"
#define SERVER_PORT 5000

// HX711 pins
#define HX711_DOUT_PIN 4  // DT/DOUT pin
#define HX711_SCK_PIN 3   // SCK pin

// Sampling rate
#define SAMPLE_RATE_HZ 80

// Status LED (optional)
#define STATUS_LED_PIN 8
#define USE_STATUS_LED true

// ============================================
// GLOBAL VARIABLES
// ============================================

HX711 scale;
Preferences prefs;
WebsocketsClient wsClient;

enum State {
  IDLE,
  TESTING,
  CALIBRATING
};

State currentState = IDLE;
unsigned long lastSampleTime = 0;
unsigned long sampleInterval = 1000 / SAMPLE_RATE_HZ;

float calibration_scale = 1.0;
long calibration_offset = 0;

// ============================================
// FUNCTION DECLARATIONS
// ============================================

void connectWiFi();
void connectWebSocket();
void onMessageReceived(WebsocketsMessage msg);
void sendReading();
void handleTare();
void handleCalibrate(float known_mass_g);
void loadCalibration();
void saveCalibration();
void setStatusLED(bool on);

// ============================================
// SETUP
// ============================================

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("\n\n=================================");
  Serial.println("Rocket Motor Test Stand - ESP32");
  Serial.println("=================================\n");

  // Initialize status LED
  #if USE_STATUS_LED
    pinMode(STATUS_LED_PIN, OUTPUT);
    digitalWrite(STATUS_LED_PIN, LOW);
  #endif

  // Initialize HX711
  Serial.println("Initializing HX711...");
  Serial.print("Pins - DOUT: ");
  Serial.print(HX711_DOUT_PIN);
  Serial.print(", SCK: ");
  Serial.println(HX711_SCK_PIN);

  scale.begin(HX711_DOUT_PIN, HX711_SCK_PIN);

  if (scale.wait_ready_timeout(1000)) {
    Serial.println("HX711 initialized successfully");
  } else {
    Serial.println("ERROR: HX711 not found!");
    Serial.println("Check wiring and try again");
  }

  scale.set_gain(128);

  // Load calibration
  loadCalibration();

  // Connect WiFi
  connectWiFi();

  // Connect WebSocket
  connectWebSocket();

  Serial.println("\nSetup complete. Ready to stream data.\n");
  setStatusLED(true);
}

// ============================================
// MAIN LOOP
// ============================================

void loop() {
  // Check WiFi
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi disconnected. Reconnecting...");
    setStatusLED(false);
    connectWiFi();
    setStatusLED(true);
  }

  // Check WebSocket
  if (!wsClient.available()) {
    Serial.println("WebSocket disconnected. Reconnecting...");
    connectWebSocket();
  }

  // Process WebSocket messages
  wsClient.poll();

  // Sample and send data
  unsigned long currentTime = millis();
  if (currentTime - lastSampleTime >= sampleInterval) {
    lastSampleTime = currentTime;

    if (scale.wait_ready_retry(3)) {
      sendReading();
    } else {
      Serial.println("WARNING: HX711 not ready");
    }
  }
}

// ============================================
// WIFI FUNCTIONS
// ============================================

void connectWiFi() {
  Serial.print("Connecting to WiFi: ");
  Serial.println(WIFI_SSID);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi connected!");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
    Serial.print("Signal strength (RSSI): ");
    Serial.print(WiFi.RSSI());
    Serial.println(" dBm");
  } else {
    Serial.println("\nERROR: Failed to connect to WiFi");
    Serial.println("Check SSID and password");
  }
}

// ============================================
// WEBSOCKET FUNCTIONS
// ============================================

void connectWebSocket() {
  Serial.print("Connecting to WebSocket server: ");
  Serial.print(SERVER_HOST);
  Serial.print(":");
  Serial.println(SERVER_PORT);

  String url = "ws://" + String(SERVER_HOST) + ":" + String(SERVER_PORT) + "/esp32";

  wsClient.onMessage(onMessageReceived);

  bool connected = wsClient.connect(url);

  if (connected) {
    Serial.println("WebSocket connected!");
  } else {
    Serial.println("ERROR: WebSocket connection failed");
    Serial.println("Check server IP and port");
  }
}

void onMessageReceived(WebsocketsMessage msg) {
  Serial.print("Received command: ");
  Serial.println(msg.data());

  StaticJsonDocument<256> doc;
  DeserializationError error = deserializeJson(doc, msg.data());

  if (error) {
    Serial.print("JSON parse error: ");
    Serial.println(error.c_str());
    return;
  }

  const char* type = doc["type"];

  if (strcmp(type, "tare") == 0) {
    handleTare();
  }
  else if (strcmp(type, "calibrate") == 0) {
    float known_mass = doc["known_mass"];
    handleCalibrate(known_mass);
  }
  else if (strcmp(type, "start_test") == 0) {
    Serial.println("Starting test recording...");
    currentState = TESTING;
  }
  else if (strcmp(type, "stop_test") == 0) {
    Serial.println("Stopping test recording");
    currentState = IDLE;
  }
  else {
    Serial.print("Unknown command: ");
    Serial.println(type);
  }
}

// ============================================
// DATA FUNCTIONS
// ============================================

void sendReading() {
  // Read from HX711
  long raw_value = scale.read();
  float mass_grams = scale.get_units();
  float force_n = (mass_grams / 1000.0) * 9.81;

  // Create JSON message
  StaticJsonDocument<128> doc;
  doc["type"] = "reading";
  doc["timestamp"] = millis();
  doc["force"] = round(force_n * 100) / 100.0;
  doc["raw"] = raw_value;

  String json;
  serializeJson(doc, json);

  // Send via WebSocket
  wsClient.send(json);

  // Debug output (comment out if too much data)
  Serial.printf("Raw: %ld, Mass: %.2fg, Force: %.2fN\n", raw_value, mass_grams, force_n);
}

// ============================================
// CALIBRATION FUNCTIONS
// ============================================

void handleTare() {
  Serial.println("Taring load cell...");

  scale.tare(10);
  calibration_offset = scale.get_offset();

  Serial.print("New offset: ");
  Serial.println(calibration_offset);

  saveCalibration();

  Serial.println("Tare complete");
}

void handleCalibrate(float known_mass_g) {
  Serial.print("Calibrating with known mass: ");
  Serial.print(known_mass_g);
  Serial.println("g");

  currentState = CALIBRATING;

  delay(500);

  long reading = scale.read_average(10);
  long offset = scale.get_offset();

  if (known_mass_g > 0) {
    calibration_scale = (reading - offset) / known_mass_g;
    scale.set_scale(calibration_scale);

    Serial.print("New scale factor: ");
    Serial.println(calibration_scale, 6);

    saveCalibration();

    Serial.println("Calibration complete");

    // Verify
    float measured = scale.get_units();
    Serial.print("Verification - Measured mass: ");
    Serial.print(measured);
    Serial.println("g");
  } else {
    Serial.println("ERROR: Known mass must be > 0");
  }

  currentState = IDLE;
}

void loadCalibration() {
  Serial.println("Loading calibration from NVS...");

  prefs.begin("test-stand", false);

  calibration_scale = prefs.getFloat("scale", 1.0);
  calibration_offset = prefs.getLong("offset", 0);

  Serial.print("Loaded scale: ");
  Serial.println(calibration_scale, 6);
  Serial.print("Loaded offset: ");
  Serial.println(calibration_offset);

  scale.set_scale(calibration_scale);
  scale.set_offset(calibration_offset);

  prefs.end();
}

void saveCalibration() {
  Serial.println("Saving calibration to NVS...");

  prefs.begin("test-stand", false);

  prefs.putFloat("scale", calibration_scale);
  prefs.putLong("offset", calibration_offset);

  prefs.end();

  Serial.println("Calibration saved");
}

// ============================================
// UTILITY FUNCTIONS
// ============================================

void setStatusLED(bool on) {
  #if USE_STATUS_LED
    digitalWrite(STATUS_LED_PIN, on ? HIGH : LOW);
  #endif
}
