/**
 * Minimal test to verify ESP32 serial communication
 * Rename this to main.cpp to use it
 */

#include <Arduino.h>

void setup() {
  Serial.begin(115200);
  delay(2000);  // Wait for serial to stabilize

  Serial.println("\n\n=================================");
  Serial.println("ESP32 Serial Test - SUCCESS!");
  Serial.println("=================================\n");
}

void loop() {
  static int count = 0;

  Serial.print("Loop count: ");
  Serial.println(count++);

  delay(1000);
}
