// ESP32 UART evidence gateway. Never creates official results or trusts reader time.
#include <Arduino.h>
#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <LittleFS.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <esp_system.h>
#include <time.h>

HardwareSerial reader(2);
JsonDocument config;
String frame;
String consoleCommand;
bool dropping = false, ready = false, storageFault = false;
uint32_t nextSync = 0, nextWifi = 0;
unsigned retrySeconds = 2;
constexpr unsigned MAX_RECORDS = 128; // Includes sent/rejected evidence; export before pruning.

bool uuidValid(const String &value) {
  if (value.length() != 36) return false;
  for (unsigned i = 0; i < 36; ++i) {
    if (i == 8 || i == 13 || i == 18 || i == 23) { if (value[i] != '-') return false; }
    else if (!isxdigit(static_cast<unsigned char>(value[i]))) return false;
  }
  return true;
}

String uuid() {
  uint8_t bytes[16]; esp_fill_random(bytes, sizeof(bytes));
  bytes[6] = (bytes[6] & 0x0f) | 0x40; bytes[8] = (bytes[8] & 0x3f) | 0x80;
  char result[37];
  snprintf(result, sizeof(result), "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x",
    bytes[0], bytes[1], bytes[2], bytes[3], bytes[4], bytes[5], bytes[6], bytes[7],
    bytes[8], bytes[9], bytes[10], bytes[11], bytes[12], bytes[13], bytes[14], bytes[15]);
  return String(result);
}

bool validOrigin(String origin) {
  if (!origin.startsWith("https://")) return false;
  origin = origin.substring(8);
  if (!origin.length()) return false;
  for (unsigned i = 0; i < origin.length(); ++i) {
    char c = origin[i];
    if (!(isalnum(static_cast<unsigned char>(c)) || c == '.' || c == '-' || c == ':')) return false;
  }
  return true;
}

bool normalize(String raw, String &uid) {
  String prefix = config["uid_prefix"] | "", suffix = config["uid_suffix"] | "";
  if (!raw.startsWith(prefix) || !raw.endsWith(suffix) || raw.length() < prefix.length() + suffix.length()) return false;
  uid = raw.substring(prefix.length(), raw.length() - suffix.length());
  String format = config["uid_format"] | "ascii";
  if (uid.isEmpty() || uid.length() > 200) return false;
  unsigned expected = config["uid_length"] | 0;
  if (expected && uid.length() != expected) return false;
  for (unsigned i = 0; i < uid.length(); ++i) {
    unsigned char c = uid[i];
    if (c < 33 || c > 126 || (format == "decimal" && !isdigit(c)) || (format == "hex" && !isxdigit(c))) return false;
  }
  String policy = config["normalization"] | "preserve";
  if (policy == "hex") {
    // Hex normalization is strict; separators must be removed by a dedicated protocol decoder.
    for (unsigned i = 0; i < uid.length(); ++i) if (!isxdigit(static_cast<unsigned char>(uid[i]))) return false;
    uid.toUpperCase();
  } else if (policy == "upper") uid.toUpperCase();
  return true;
}

unsigned recordCount() {
  unsigned count = 0;
  File root = LittleFS.open("/"); File file = root.openNextFile();
  while (file) { if (String(file.path()) != "/config.json") count++; file.close(); file = root.openNextFile(); }
  return count;
}

void capture(const String &raw) {
  if (storageFault) return;
  String uid;
  if (!normalize(raw, uid)) { Serial.println("Scan rejected: UID profile mismatch."); return; }
  if (recordCount() >= MAX_RECORDS || LittleFS.totalBytes() - LittleFS.usedBytes() < 8192) {
    storageFault = true; Serial.println("CAPTURE STOPPED: evidence storage full. Export records before maintenance."); return;
  }
  JsonDocument event;
  event["backend_url"] = config["backend_url"];
  event["device_id"] = config["device_id"];
  JsonObject payload = event["payload"].to<JsonObject>();
  String id = uuid();
  payload["message_id"] = id;
  payload["race_id"] = config["race_id"];
  payload["ring_uid"] = uid;
  payload["original_scan"] = raw;
  payload["offline_buffered"] = true;
  bool simulated = config["simulated"] | false;
  payload["adapter_type"] = simulated ? "simulator" : "serial";
  payload["protocol"] = config["protocol"];
  payload["capture_mode"] = simulated ? "simulated" : (config["capture_mode"] | "operator");
  String path = "/" + id;
  File file = LittleFS.open(path + ".tmp", "w");
  bool written = file && serializeJson(event, file) == measureJson(event);
  file.flush(); file.close();
  if (!written || !LittleFS.rename(path + ".tmp", path + ".pending")) {
    storageFault = true; Serial.println("CAPTURE STOPPED: storage failure; inspect retained temporary evidence."); return;
  }
  Serial.println("Scan queued. Pending evidence only.");
}

void recoverTemporaryFiles() {
  File root = LittleFS.open("/"); File file = root.openNextFile();
  while (file) {
    String path = file.path();
    if (path.endsWith(".tmp")) {
      JsonDocument event;
      bool complete = !deserializeJson(event, file) && uuidValid(event["payload"]["message_id"].as<String>())
        && event["payload"]["ring_uid"].is<String>() && event["backend_url"].is<String>();
      file.close();
      String target = path.substring(0, path.length() - 4) + (complete ? ".pending" : ".corrupt");
      if (!LittleFS.rename(path, target)) storageFault = true;
    } else file.close();
    file = root.openNextFile();
  }
}

void syncOne() {
  File root = LittleFS.open("/"); File file = root.openNextFile();
  while (file) {
    String path = file.path();
    if (!path.endsWith(".pending")) { file.close(); file = root.openNextFile(); continue; }
    JsonDocument event;
    bool valid = file.size() <= 4096 && !deserializeJson(event, file);
    file.close();
    if (!valid) {
      if (!LittleFS.rename(path, path.substring(0, path.length() - 8) + ".corrupt")) storageFault = true;
      Serial.println("Corrupt evidence retained for inspection."); return;
    }
    // Old queues never follow a changed origin or device configuration.
    if (event["backend_url"].as<String>() != config["backend_url"].as<String>() || event["device_id"].as<String>() != config["device_id"].as<String>()) {
      file = root.openNextFile(); continue;
    }
    String body; serializeJson(event["payload"], body);
    WiFiClientSecure tls;
    tls.setCACert(config["root_ca"].as<const char *>());
    HTTPClient http;
    http.setConnectTimeout(3000); http.setTimeout(3000);
    http.setFollowRedirects(HTTPC_DISABLE_FOLLOW_REDIRECTS);
    String url = event["backend_url"].as<String>() + "/devices/" + event["device_id"].as<String>() + "/arrivals";
    if (!http.begin(tls, url)) return;
    http.addHeader("Content-Type", "application/json");
    http.addHeader("X-Device-Token", config["device_token"].as<String>());
    int status = http.POST(body);
    String state;
    if (status == 202 && http.getSize() > 0 && http.getSize() <= 2048) {
      JsonDocument ack;
      if (!deserializeJson(ack, http.getString()) && uuidValid(ack["event_id"].as<String>())
          && ack["status"] == "pending" && ack["official_result_created"].is<bool>()
          && !ack["official_result_created"].as<bool>()) state = ".sent";
    } else if (status == 404 || status == 409 || status == 422) state = ".rejected";
    http.end();
    if (state.length()) {
      if (!LittleFS.rename(path, path.substring(0, path.length() - 8) + state)) storageFault = true;
      retrySeconds = 2;
      Serial.println(state == ".sent" ? "Evidence acknowledged; retained locally." : "Evidence rejected; retained locally.");
    } else {
      retrySeconds = min(300U, retrySeconds * 2);
      Serial.println("Delivery unconfirmed; evidence retained for retry.");
    }
    return;
  }
  retrySeconds = 2;
}

// Local USB serial console only. Never export configuration/Wi-Fi/device secrets.
void maintenance(const String &command) {
  if (command == "status") {
    Serial.printf("records=%u limit=%u storage_fault=%s wifi=%s\n", recordCount(), MAX_RECORDS,
      storageFault ? "true" : "false", WiFi.status() == WL_CONNECTED ? "connected" : "offline");
  } else if (command == "export" || command == "prune-sent CONFIRM") {
    File root = LittleFS.open("/"); File file = root.openNextFile();
    while (file) {
      String path = file.path();
      if (path != "/config.json") {
        if (command == "export") {
          Serial.println(path);
          while (file.available()) Serial.write(file.read());
          Serial.println();
        }
        file.close();
        if (command == "prune-sent CONFIRM" && path.endsWith(".sent")) LittleFS.remove(path);
      } else file.close();
      file = root.openNextFile();
    }
    // Fault stays latched until reboot so storage is checked before resuming capture.
    Serial.println("Maintenance complete. Reboot after checking storage before capture resumes.");
  } else Serial.println("Commands: status, export, prune-sent CONFIRM. Export evidence before pruning sent records.");
}

void setup() {
  Serial.begin(115200);
  if (!LittleFS.begin(false)) { Serial.println("LittleFS unavailable. No auto-format; provision filesystem first."); return; }
  File file = LittleFS.open("/config.json", "r");
  bool loaded = file && file.size() <= 8192 && !deserializeJson(config, file); file.close();
  String mode = config["capture_mode"] | "operator", policy = config["normalization"] | "preserve", format = config["uid_format"] | "ascii";
  String secret = config["device_token"] | "", protocol = config["protocol"] | "", ca = config["root_ca"] | "";
  int terminator = config["terminator"] | 10, baud = config["reader_baud"] | 9600;
  if (!loaded || !validOrigin(config["backend_url"].as<String>())
      || !config["simulated"].is<bool>()
      || !uuidValid(config["device_id"].as<String>()) || !uuidValid(config["race_id"].as<String>())
      || secret.length() < 16 || secret.length() > 256 || secret.startsWith("REPLACE")
      || !ca.startsWith("-----BEGIN CERTIFICATE-----") || ca.indexOf("REPLACE") >= 0
      || protocol.isEmpty() || protocol.length() > 120 || (mode != "operator" && mode != "automatic")
      || (policy != "preserve" && policy != "upper" && policy != "hex")
      || (format != "ascii" && format != "decimal" && format != "hex")
      || (terminator != 10 && terminator != 13) || baud < 1 || baud > 4000000) {
    Serial.println("Invalid/missing configuration. Capture disabled."); return;
  }
  recoverTemporaryFiles();
  reader.setRxBufferSize(4096);
  reader.begin(baud, SERIAL_8N1, config["reader_rx"] | 16, config["reader_tx"] | 17);
  WiFi.mode(WIFI_STA); WiFi.setAutoReconnect(true);
  WiFi.begin(config["wifi_ssid"].as<const char *>(), config["wifi_password"].as<const char *>());
  configTime(0, 0, "pool.ntp.org", "time.nist.gov"); // TLS validity only, not arrival time.
  ready = true; Serial.println("UART evidence gateway ready. Official finalization disabled.");
}

void loop() {
  if (!ready) { delay(100); return; }
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') { consoleCommand.trim(); maintenance(consoleCommand); consoleCommand = ""; }
    else if (consoleCommand.length() < 80) consoleCommand += c;
  }
  while (reader.available()) {
    char c = reader.read();
    if (c == (config["terminator"] | 10)) {
      if (!dropping) {
        while (frame.endsWith("\r") || frame.endsWith("\n")) frame.remove(frame.length() - 1);
        if (frame.length()) capture(frame);
      }
      frame = ""; dropping = false;
    } else if (!dropping && !(frame.isEmpty() && (c == '\r' || c == '\n'))) {
      if (frame.length() >= 1024) { frame = ""; dropping = true; Serial.println("Oversized frame rejected."); }
      else frame += c;
    }
  }
  uint32_t now = millis();
  if (WiFi.status() != WL_CONNECTED && static_cast<int32_t>(now - nextWifi) >= 0) {
    WiFi.reconnect(); nextWifi = now + 15000;
  }
  if (WiFi.status() == WL_CONNECTED && time(nullptr) > 1700000000 && static_cast<int32_t>(now - nextSync) >= 0) {
    syncOne(); nextSync = millis() + retrySeconds * 1000;
  }
  delay(2);
}
