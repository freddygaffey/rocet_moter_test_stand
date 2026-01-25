/**
 * Rocket Motor Test Stand - ESP32-C3 Firmware
 *
 * Reads load cell data via HX711 and streams to server via WebSocket.
 * Uses bogde/HX711 library - no custom driver needed.
 */

#include <Arduino.h>
#include <WiFi.h>
#include <ArduinoWebsockets.h>
#include <ArduinoJson.h>
#include <HX711.h>
#include <Preferences.h>
#include "config.h"

using namespace websockets;

// Hardware
HX711 scale;
Preferences prefs;
WebsocketsClient wsClient;

// State
enum State {
  IDLE,
  TESTING,
  CALIBRATING
};

State currentState = IDLE;
unsigned long lastSampleTime = 0;
unsigned long sampleInterval = 1000 / SAMPLE_RATE_HZ;

// Calibration
float calibration_scale = 1.0;
long calibration_offset = 0;

// Function declarations
void connectWiFi();
void connectWebSocket();
void onMessageReceived(WebsocketsMessage msg);
void sendReading();
void handleTare();
void handleCalibrate(float known_mass_g);
void loadCalibration();
void saveCalibration();
void setStatusLED(bool on);

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("\n\n=================================");
  Serial.println("Rocket Motor Test Stand - ESP32");
  Serial.println("=================================\n");

  // Initialize status LED if enabled
  #if USE_STATUS_LED
    pinMode(STATUS_LED_PIN, OUTPUT);
    digitalWrite(STATUS_LED_PIN, LOW);
  #endif

  // Initialize HX711 load cell amplifier (using library)
  Serial.println("Initializing HX711...");
  scale.begin(HX711_DOUT_PIN, HX711_SCK_PIN);

  if (scale.wait_ready_timeout(1000)) {
    Serial.println("HX711 initialized successfully");
  } else {
    Serial.println("ERROR: HX711 not found!");
  }

  // Set gain (128 = Channel A with gain 128)
  scale.set_gain(128);

  // Load calibration from non-volatile storage
  loadCalibration();

  // Connect to WiFi
  connectWiFi();

  // Connect to WebSocket server
  connectWebSocket();

  Serial.println("\nSetup complete. Ready to stream data.\n");
  setStatusLED(true);
}

void loop() {
  // Check WiFi connection
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi disconnected. Reconnecting...");
    setStatusLED(false);
    connectWiFi();
    setStatusLED(true);
  }

  // Check WebSocket connection
  if (!wsClient.available()) {
    Serial.println("WebSocket disconnected. Reconnecting...");
    connectWebSocket();
  }

  // Process incoming WebSocket messages
  wsClient.poll();

  // Sample and send data at configured rate
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
    Serial.println("Please check SSID and password in config.h");
  }
}

void connectWebSocket() {
  Serial.print("Connecting to WebSocket server: ");
  Serial.print(SERVER_HOST);
  Serial.print(":");
  Serial.println(SERVER_PORT);

  // Build WebSocket URL
  String url = "ws://" + String(SERVER_HOST) + ":" + String(SERVER_PORT) + "/esp32";

  // Set message callback
  wsClient.onMessage(onMessageReceived);

  // Connect
  bool connected = wsClient.connect(url);

  if (connected) {
    Serial.println("WebSocket connected!");
  } else {
    Serial.println("ERROR: WebSocket connection failed");
    Serial.println("Check server IP and port in config.h");
  }
}

void onMessageReceived(WebsocketsMessage msg) {
  Serial.print("Received command: ");
  Serial.println(msg.data());

  // Parse JSON command
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

void sendReading() {
  // Read raw value from HX711 (using library)
  long raw_value = scale.read();

  // Get calibrated value in grams (using library's calibration)
  float mass_grams = scale.get_units();

  // Convert to force in Newtons (F = mg, g = 9.81 m/s²)
  float force_n = (mass_grams / 1000.0) * 9.81;

  // Create JSON message
  StaticJsonDocument<128> doc;
  doc["type"] = "reading";
  doc["timestamp"] = millis();
  doc["force"] = round(force_n * 100) / 100.0;  // Round to 2 decimals
  doc["raw"] = raw_value;

  String json;
  serializeJson(doc, json);

  // Send via WebSocket
  wsClient.send(json);

  // Debug output (optional - comment out for production)
  // Serial.printf("Raw: %ld, Mass: %.2fg, Force: %.2fN\n", raw_value, mass_grams, force_n);
}

void handleTare() {
  Serial.println("Taring load cell...");

  // Use HX711 library's tare function
  scale.tare(10);  // Average 10 readings

  calibration_offset = scale.get_offset();

  Serial.print("New offset: ");
  Serial.println(calibration_offset);

  // Save to non-volatile storage
  saveCalibration();

  Serial.println("Tare complete");
}

void handleCalibrate(float known_mass_g) {
  Serial.print("Calibrating with known mass: ");
  Serial.print(known_mass_g);
  Serial.println("g");

  currentState = CALIBRATING;

  // Wait for stable reading
  delay(500);

  // Get current reading (average of 10)
  long reading = scale.read_average(10);
  long offset = scale.get_offset();

  // Calculate scale factor
  // scale_factor = (reading - offset) / known_mass_g
  if (known_mass_g > 0) {
    calibration_scale = (reading - offset) / known_mass_g;
    scale.set_scale(calibration_scale);

    Serial.print("New scale factor: ");
    Serial.println(calibration_scale, 6);

    // Save to non-volatile storage
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

  // Apply to HX711 (using library functions)
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

void setStatusLED(bool on) {
  #if USE_STATUS_LED
    digitalWrite(STATUS_LED_PIN, on ? HIGH : LOW);
  #endif
}
