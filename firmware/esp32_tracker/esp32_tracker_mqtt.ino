#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BNO055.h>
#include <AccelStepper.h>
#include <HardwareSerial.h>
#include <Preferences.h>

// ==========================================
// 1. KONFIGURASI JARINGAN & MQTT BROKER
// ==========================================
const char* ssid         = "HILTRON";              // Nama Hotspot / WiFi Anda
const char* password     = "12345678";             // Password Hotspot
const char* mqtt_broker  = "broker.emqx.io";       // EMQX Public Broker (Free & Reliable)
const int   mqtt_port    = 1883;

// Topik MQTT (Harus sama persis dengan frontend mqtt-bridge.js)
const char* topic_command   = "hiltron/tracker/command";
const char* topic_telemetry = "hiltron/tracker/telemetry";
const char* topic_status    = "hiltron/tracker/status";

WiFiClient espClient;
PubSubClient mqttClient(espClient);

// ==========================================
// 2. OBJEK HARDWARE (GPS, BNO055, NVS & STEPPER)
// ==========================================
// --- GPS NEO-6M / Serial2 ---
HardwareSerial SerialGPS(2);
#define GPS_RX_PIN 16
#define GPS_TX_PIN 17

bool  gps_valid = false;
float gps_lat   = 0.0;
float gps_lon   = 0.0;
int   gps_sats  = 0;
String nmeaSentence = "";

// --- Sensor Orientasi BNO055 ---
#define BNO055_AVAILABLE true
#define I2C_SDA_PIN 21
#define I2C_SCL_PIN 22

// Penyesuaian / Offset Orientasi Fisik Sensor
const float AZIMUTH_OFFSET  = 0.0;
const float ALTITUDE_OFFSET = 0.0;
const bool  INVERT_ALTITUDE = false;

// Konfigurasi Arah Putaran Motor Stepper
const bool INVERT_ALT_MOTOR = true;  
const bool INVERT_AZ_MOTOR  = true; 

float last_target_az  = -999.0;
float last_target_alt = -999.0;

// --- STATUS MODE CELESTIAL LIVE LOCK TRACKING ---
bool is_live_tracking = false;
unsigned long last_tracking_packet_ms = 0;

#if BNO055_AVAILABLE
Adafruit_BNO055 bnoA = Adafruit_BNO055(55, 0x28, &Wire);
Adafruit_BNO055 bnoB = Adafruit_BNO055(55, 0x29, &Wire);
Adafruit_BNO055* bno = &bnoA;
bool bno_active = false;
bool calibration_loaded = false;
#endif

// Flash NVS untuk Kalibrasi BNO055
Preferences preferences;

// Motor Stepper 28BYJ-48 + ULN2003
// Motor 1 — Azimuth (Horizontal)
#define motorAzPin1 13
#define motorAzPin2 12
#define motorAzPin3 14
#define motorAzPin4 27
AccelStepper stepperAzimuth(AccelStepper::HALF4WIRE, motorAzPin1, motorAzPin3, motorAzPin2, motorAzPin4);

// Motor 2 — Altitude (Vertikal)
#define motorAltPin1 26
#define motorAltPin2 25
#define motorAltPin3 33
#define motorAltPin4 32
AccelStepper stepperAltitude(AccelStepper::HALF4WIRE, motorAltPin1, motorAltPin3, motorAltPin2, motorAltPin4);

float current_azimuth  = 0.0;
float current_altitude = 0.0;
unsigned long lastSensorRead    = 0;
unsigned long lastTelemetrySend = 0;
unsigned long lastMqttReconnect = 0;

const float STEPS_PER_DEGREE = 4096.0 / 360.0; // ~11.377 step/derajat

// Prototipe Fungsi
void processGPS();
void parseNMEALine(String line);
float convertDegMinToDec(String degMin, char dir);
void readSensor();
void sendTelemetry();
void setTargetPosition(float target_az, float target_alt, bool is_live_stream = false);
void handleIncomingCommand(const char* payload);
void saveCalibrationOffsets();
void clearCalibrationOffsets();
void reconnectMQTT();
void mqttCallback(char* topic, byte* payload, unsigned int length);

// ==========================================
// 3. FUNGSI SETUP
// ==========================================
void setup() {
    Serial.begin(115200);
    delay(1000);

    Serial.println("\n=======================================================");
    Serial.println("  HILTRON — ESP32 CLOUD MQTT TRACKER (EMQX IoT BRIDGE) ");
    Serial.println("=======================================================");

    // Inisialisasi GPS
    Serial.println("[Hardware] Inisialisasi GPS (UART2 RX=16, TX=17, 9600 baud)...");
    SerialGPS.begin(9600, SERIAL_8N1, GPS_RX_PIN, GPS_TX_PIN);

    // Inisialisasi Motor Stepper
    Serial.println("[Hardware] Inisialisasi Motor Stepper...");
    stepperAzimuth.setMaxSpeed(1000.0);
    stepperAzimuth.setAcceleration(300.0);
    stepperAltitude.setMaxSpeed(1000.0);
    stepperAltitude.setAcceleration(300.0);

    // Inisialisasi Sensor BNO055
#if BNO055_AVAILABLE
    Serial.println("[Hardware] Inisialisasi Sensor Orientasi BNO055...");
    Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
    Wire.setClock(100000);
    delay(100);

    if (bnoA.begin()) {
        bno = &bnoA;
        bno_active = true;
        Serial.println("[Hardware] BNO055 TERDETEKSI pada alamat 0x28.");
    } else if (bnoB.begin()) {
        bno = &bnoB;
        bno_active = true;
        Serial.println("[Hardware] BNO055 TERDETEKSI pada alamat 0x29.");
    } else {
        Serial.println("[WARN] BNO055 Tidak terdeteksi! Menggunakan perhitungan Open-Loop Stepper.");
        bno_active = false;
    }

    if (bno_active && bno != nullptr) {
        bno->setExtCrystalUse(true);
        preferences.begin("bno055", true);
        bool hasSavedCalib = preferences.getBool("valid", false);
        if (hasSavedCalib) {
            adafruit_bno055_offsets_t calibData;
            preferences.getBytes("calib", &calibData, sizeof(adafruit_bno055_offsets_t));
            bno->setSensorOffsets(calibData);
            calibration_loaded = true;
            Serial.println("[BNO055] >> Profil Kalibrasi Flash NVS Ditemukan & DIKUNCI!");
        }
        preferences.end();
        readSensor();
    }
#endif

    // Setup Wi-Fi
    Serial.print("[WiFi] Menghubungkan ke: ");
    Serial.println(ssid);
    WiFi.disconnect(true);
    delay(200);
    WiFi.mode(WIFI_STA);
    WiFi.setAutoReconnect(true);
    if (strlen(password) > 0) {
        WiFi.begin(ssid, password);
    } else {
        WiFi.begin(ssid);
    }

    int retryCount = 0;
    while (WiFi.status() != WL_CONNECTED && retryCount < 40) {
        delay(500);
        Serial.print(".");
        retryCount++;
    }

    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("\n[WiFi] Berhasil Terhubung!");
        Serial.print("  IP Address: ");
        Serial.println(WiFi.localIP());
    } else {
        Serial.println("\n[ERROR] WiFi Gagal Terhubung! Akan dicoba ulang di background.");
    }

    // Setup MQTT Client
    mqttClient.setServer(mqtt_broker, mqtt_port);
    mqttClient.setCallback(mqttCallback);
    mqttClient.setBufferSize(512); // PENTING: buffer 512 bytes untuk payload JSON telemetri

    Serial.println("[Sistem] HILTRON ESP32 MQTT Siap! Menghubungkan ke Broker EMQX...");
}

// ==========================================
// 4. MAIN LOOP
// ==========================================
void loop() {
    // Eksekusi langkah motor stepper terus-menerus tanpa delay
    stepperAzimuth.run();
    stepperAltitude.run();

    // Pertahankan koneksi MQTT
    if (WiFi.status() == WL_CONNECTED) {
        if (!mqttClient.connected()) {
            unsigned long now = millis();
            if (now - lastMqttReconnect > 4000) {
                lastMqttReconnect = now;
                reconnectMQTT();
            }
        } else {
            mqttClient.loop();
        }
    }

    // Baca data NMEA dari GPS
    processGPS();

    unsigned long currentMillis = millis();

    // Baca sensor orientasi tiap 100ms
    if (currentMillis - lastSensorRead >= 100) {
        lastSensorRead = currentMillis;
        readSensor();

#if BNO055_AVAILABLE
        if (!calibration_loaded && bno_active && bno != nullptr) {
            uint8_t sys, gyro, accel, mag;
            bno->getCalibration(&sys, &gyro, &accel, &mag);
            if (mag >= 3 && gyro >= 3 && accel >= 2) {
                Serial.println("\n[BNO055] Auto-Saving Kalibrasi Optimal ke Flash NVS...");
                saveCalibrationOffsets();
            }
        }
#endif
    }

    // Kirim telemetri via MQTT tiap 1 detik
    if (currentMillis - lastTelemetrySend >= 1000) {
        lastTelemetrySend = currentMillis;
        sendTelemetry();
    }

    // Safety Watchdog: Jika live tracking aktif namun stream terputus > 20 detik, nonaktifkan otomatis
    if (is_live_tracking && (currentMillis - last_tracking_packet_ms > 20000)) {
        is_live_tracking = false;
        Serial.println("[WATCHDOG] Stream koordinat terhenti > 20s. Mode Live Tracking otomatis dinonaktifkan.");
    }
}

// ==========================================
// 5. MANAJEMEN KONEKSI MQTT
// ==========================================
void reconnectMQTT() {
    if (WiFi.status() != WL_CONNECTED) return;

    String clientId = "HILTRON_ESP32_" + String(random(0xffff), HEX);
    Serial.printf("[MQTT] Menghubungkan ke Broker %s:%d (ID: %s)...\n", mqtt_broker, mqtt_port, clientId.c_str());

    // Connect dengan LWT (Last Will & Testament): Jika koneksi putus tiba-tiba, laporkan "offline"
    if (mqttClient.connect(clientId.c_str(), topic_status, 1, true, "offline")) {
        Serial.println("[MQTT] >> BERHASIL TERHUBUNG KE EMQX CLOUD BROKER! <<");
        
        // Publikasikan status online
        mqttClient.publish(topic_status, "online", true);

        // Berlangganan (Subscribe) ke topik perintah dari Web Vercel
        mqttClient.subscribe(topic_command, 1);
        Serial.printf("[MQTT] Berhasil subscribe ke: %s\n", topic_command);

        sendTelemetry();
    } else {
        Serial.printf("[MQTT] Gagal konek, rc=%d. Coba lagi dalam 4 detik...\n", mqttClient.state());
    }
}

// ==========================================
// 6. PENERIMA PESAN MQTT (CALLBACK)
// ==========================================
void mqttCallback(char* topic, byte* payload, unsigned int length) {
    char message[length + 1];
    memcpy(message, payload, length);
    message[length] = '\0';

    Serial.printf("\n[MQTT Rx] Topik: %s | Pesan: %s\n", topic, message);
    handleIncomingCommand(message);
}

void handleIncomingCommand(const char* payload) {
    StaticJsonDocument<256> doc;
    DeserializationError error = deserializeJson(doc, payload);

    if (error) {
        Serial.print("[JSON Error]: ");
        Serial.println(error.f_str());
        return;
    }

    const char* command = doc["command"];
    if (!command) return;

    // Perintah Gerakkan Tracker ke Posisi Hilal (One-Shot Go-To)
    if (strcmp(command, "POINT_HILAL") == 0) {
        float target_azimuth = doc["target_azimuth"];
        float target_altitude = doc["target_altitude"];

        Serial.println("\n>>> PERINTAH ARAHKAN HILAL (GO-TO) DITERIMA <<<");
        Serial.printf("Target Azimuth  : %.2f\n", target_azimuth);
        Serial.printf("Target Altitude : %.2f\n", target_altitude);

        setTargetPosition(target_azimuth, target_altitude, false);
    }
    // Perintah Mulai Celestial Live Lock Tracking
    else if (strcmp(command, "START_TRACKING") == 0) {
        float target_azimuth = doc["target_azimuth"];
        float target_altitude = doc["target_altitude"];
        is_live_tracking = true;
        last_tracking_packet_ms = millis();

        Serial.println("\n=======================================================");
        Serial.println(">>> [TRACKER] MODE CELESTIAL LIVE LOCK TRACKING: AKTIF <<<");
        Serial.printf("  Target Awal Hilal: Azimuth=%.2f°, Altitude=%.2f°\n", target_azimuth, target_altitude);
        Serial.println("=======================================================");

        setTargetPosition(target_azimuth, target_altitude, false);
    }
    // Perintah Update Stream Koordinat Live Tracking
    else if (strcmp(command, "LIVE_TRACKING") == 0) {
        float target_azimuth = doc["target_azimuth"];
        float target_altitude = doc["target_altitude"];
        is_live_tracking = true;
        last_tracking_packet_ms = millis();

        setTargetPosition(target_azimuth, target_altitude, true);
    }
    // Perintah Hentikan Live Tracking Hilal
    else if (strcmp(command, "STOP_TRACKING") == 0) {
        is_live_tracking = false;
        Serial.println("\n>>> [TRACKER] LIVE LOCK TRACKING DIHENTIKAN. Posisi Motor Mengunci. <<<");
    }
    // Perintah Simpan Kalibrasi BNO055
    else if (strcmp(command, "SAVE_CALIBRATION") == 0) {
        Serial.println("[MQTT] Menerima instruksi simpan kalibrasi...");
        saveCalibrationOffsets();
    }
    // Perintah Reset Kalibrasi NVS
    else if (strcmp(command, "CLEAR_CALIBRATION") == 0) {
        Serial.println("[MQTT] Menerima instruksi reset kalibrasi...");
        clearCalibrationOffsets();
    }
    // Perintah Kalibrasi Titik Nol (Set Home)
    else if (strcmp(command, "SET_HOME") == 0) {
        Serial.println("\n[Motor] Menetapkan posisi fisik saat ini sebagai Titik Nol (0° Ufuk & Hadap Utara)...");
        stepperAltitude.setCurrentPosition(0);
        stepperAzimuth.setCurrentPosition(0);
        last_target_az  = -999.0;
        last_target_alt = -999.0;
        current_azimuth  = 0.0;
        current_altitude = 0.0;
    }
}

// ==========================================
// 7. LOGIKA PERGERAKAN MOTOR
// ==========================================
void setTargetPosition(float target_az, float target_alt, bool is_live_stream) {
    // 1. Proteksi batas fisik altitude (0° s/d 90°):
    float safe_alt = target_alt;
    if (safe_alt < 0.0)  safe_alt = 0.0;
    if (safe_alt > 90.0) safe_alt = 90.0;

    // 2. Normalisasi Azimuth terhadap Utara (0°):
    float norm_az = target_az;
    while (norm_az < 0.0)    norm_az += 360.0;
    while (norm_az >= 360.0) norm_az -= 360.0;

    // Rute putaran terpendek -180° s/d +180° dari Utara:
    float azFromNorth = norm_az;
    if (azFromNorth > 180.0) azFromNorth -= 360.0;

    long targetStepAzimuth  = (long)(azFromNorth * STEPS_PER_DEGREE) * (INVERT_AZ_MOTOR ? -1 : 1);
    long targetStepAltitude = (long)(safe_alt * STEPS_PER_DEGREE) * (INVERT_ALT_MOTOR ? -1 : 1);

    // 3. Cek apakah target step motor sama persis:
    if (targetStepAzimuth == stepperAzimuth.targetPosition() && targetStepAltitude == stepperAltitude.targetPosition()) {
        if (!is_live_stream) {
            Serial.println("[Motor] Target sudah tercapai (posisi step sama). Motor mengunci.");
        }
        return;
    }

    if (!is_live_stream) {
        Serial.println("\n>>> INSTRUKSI TARGET HILAL BARU DITERIMA <<<");
        Serial.printf("  Target Azimuth  : %.2f° (Relatif Utara: %.2f°, Step: %ld)\n", norm_az, azFromNorth, targetStepAzimuth);
        Serial.printf("  Target Altitude : %.2f° (Safe Alt: %.2f°, Step: %ld)\n", target_alt, safe_alt, targetStepAltitude);
    } else {
        Serial.printf("[LIVE LOCK] Step Baru -> AzStep: %ld, AltStep: %ld (Az: %.2f°, Alt: %.2f°)\n",
                      targetStepAzimuth, targetStepAltitude, norm_az, safe_alt);
    }

    // Gerakkan motor absolut ke target langkah
    stepperAzimuth.moveTo(targetStepAzimuth);
    stepperAltitude.moveTo(targetStepAltitude);

    last_target_az  = target_az;
    last_target_alt = safe_alt;
}

void readSensor() {
#if BNO055_AVAILABLE
    if (bno_active && bno != nullptr) {
        sensors_event_t event;
        bno->getEvent(&event);
    }
#endif

    float currentAzDeg = ((float)stepperAzimuth.currentPosition() / STEPS_PER_DEGREE) * (INVERT_AZ_MOTOR ? -1.0 : 1.0);
    if (currentAzDeg < 0.0)    currentAzDeg += 360.0;
    if (currentAzDeg >= 360.0) currentAzDeg -= 360.0;
    current_azimuth = currentAzDeg;

    current_altitude = ((float)stepperAltitude.currentPosition() / STEPS_PER_DEGREE) * (INVERT_ALT_MOTOR ? -1.0 : 1.0);
}

void sendTelemetry() {
    uint8_t system = 0, gyro = 0, accel = 0, mag = 0;
#if BNO055_AVAILABLE
    if (bno_active && bno != nullptr) {
        bno->getCalibration(&system, &gyro, &accel, &mag);
        if (calibration_loaded) {
            system = 3; gyro = 3; accel = 3; mag = 3;
        }
    }
#endif

    char telemetry[380];
    sprintf(telemetry, 
        "{\"type\":\"telemetry\",\"azimuth\":%.2f,\"altitude\":%.2f,\"cal_sys\":%d,\"cal_gyro\":%d,\"cal_accel\":%d,\"cal_mag\":%d,\"cal_locked\":%s,\"gps_valid\":%s,\"gps_lat\":%.6f,\"gps_lon\":%.6f,\"gps_sats\":%d,\"is_tracking\":%s}",
        current_azimuth, current_altitude, system, gyro, accel, mag,
        calibration_loaded ? "true" : "false",
        gps_valid ? "true" : "false", gps_lat, gps_lon, gps_sats,
        is_live_tracking ? "true" : "false"
    );

    if (mqttClient.connected()) {
        mqttClient.publish(topic_telemetry, telemetry);
    }
}

// ==========================================
// 8. PARSER NMEA GPS
// ==========================================
void processGPS() {
    while (SerialGPS.available()) {
        char c = SerialGPS.read();
        if (c == '\r') continue;
        if (c == '\n') {
            if (nmeaSentence.length() > 0) {
                parseNMEALine(nmeaSentence);
                nmeaSentence = "";
            }
        } else {
            if (nmeaSentence.length() < 120) {
                nmeaSentence += c;
            } else {
                nmeaSentence = "";
            }
        }
    }
}

void parseNMEALine(String line) {
    if (line.startsWith("$GPRMC") || line.startsWith("$GNRMC")) {
        int commaIdx[12];
        int count = 0;
        for (int i = 0; i < line.length() && count < 12; i++) {
            if (line.charAt(i) == ',') {
                commaIdx[count++] = i;
            }
        }
        if (count >= 6) {
            String status = line.substring(commaIdx[1] + 1, commaIdx[2]);
            if (status == "A") {
                gps_valid = true;
                String rawLat = line.substring(commaIdx[2] + 1, commaIdx[3]);
                String ns     = line.substring(commaIdx[3] + 1, commaIdx[4]);
                String rawLon = line.substring(commaIdx[4] + 1, commaIdx[5]);
                String ew     = line.substring(commaIdx[5] + 1, commaIdx[6]);

                if (rawLat.length() > 0 && rawLon.length() > 0) {
                    gps_lat = convertDegMinToDec(rawLat, ns.length() > 0 ? ns.charAt(0) : 'N');
                    gps_lon = convertDegMinToDec(rawLon, ew.length() > 0 ? ew.charAt(0) : 'E');
                }
            } else {
                gps_valid = false;
            }
        }
    }

    if (line.startsWith("$GPGGA") || line.startsWith("$GNGGA")) {
        int commaIdx[10];
        int count = 0;
        for (int i = 0; i < line.length() && count < 10; i++) {
            if (line.charAt(i) == ',') {
                commaIdx[count++] = i;
            }
        }
        if (count >= 7) {
            String satsStr = line.substring(commaIdx[6] + 1, commaIdx[7]);
            if (satsStr.length() > 0) {
                gps_sats = satsStr.toInt();
            }
        }
    }
}

float convertDegMinToDec(String degMin, char dir) {
    float val = degMin.toFloat();
    int degrees = (int)(val / 100.0);
    float minutes = val - (degrees * 100.0);
    float dec = degrees + (minutes / 60.0);
    if (dir == 'S' || dir == 'W') {
        dec = -dec;
    }
    return dec;
}

// ==========================================
// 9. KALIBRASI BNO055 (FLASH NVS)
// ==========================================
void saveCalibrationOffsets() {
#if BNO055_AVAILABLE
    if (bno_active && bno != nullptr) {
        adafruit_bno055_offsets_t calibData;
        if (bno->getSensorOffsets(calibData)) {
            preferences.begin("bno055", false);
            preferences.putBytes("calib", &calibData, sizeof(adafruit_bno055_offsets_t));
            preferences.putBool("valid", true);
            preferences.end();

            calibration_loaded = true;
            Serial.println("[BNO055] SUKSES: Data kalibrasi disimpan permanen ke Flash NVS!");
            sendTelemetry();
        }
    }
#endif
}

void clearCalibrationOffsets() {
#if BNO055_AVAILABLE
    preferences.begin("bno055", false);
    preferences.clear();
    preferences.end();
    calibration_loaded = false;
    Serial.println("[BNO055] Data kalibrasi di NVS berhasil di-reset!");
    sendTelemetry();
#endif
}
