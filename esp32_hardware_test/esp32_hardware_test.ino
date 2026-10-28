#include <WiFi.h>

void setup() {
  Serial.begin(115200);
  delay(1500);

  Serial.println("\nQT Py ESP32 Pico test");
  Serial.printf("Flash: %u MB\n", ESP.getFlashChipSize() / (1024 * 1024));
  Serial.printf("PSRAM: %u MB\n", ESP.getPsramSize() / (1024 * 1024));
  Serial.printf("Free PSRAM: %u bytes\n", ESP.getFreePsram());

  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  delay(100);

  Serial.println("\nScanning Wi-Fi...");
  int count = WiFi.scanNetworks();

  if (count <= 0) {
    Serial.println("No networks found.");
  } else {
    for (int i = 0; i < count; i++) {
      Serial.printf("%2d: %-32s RSSI %d dBm %s\n",
                    i + 1,
                    WiFi.SSID(i).c_str(),
                    WiFi.RSSI(i),
                    WiFi.encryptionType(i) == WIFI_AUTH_OPEN
                      ? "open" : "secured");
    }
  }
}

void loop() {
}