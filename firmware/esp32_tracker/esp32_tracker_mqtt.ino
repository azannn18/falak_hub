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
// 1. KONFIGURASI WI-FI & BROKER MQTT EMQX
// ==========================================
const char* ssid     = "HILTRON";          // Nama Wi-Fi / Mobile Hotspot HP Anda
const char* password = "12345678";         // Password Wi-Fi

// Broker MQTT Publik EMQX (100% Gratis, Tanpa Daftar, Tanpa Kartu Kredit)
const char* mqtt_server = "broker.emqx.io";
const int   mqtt_port   = 1883;

// Topik MQTT Khusus HILTRON
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

// --- KONFIGURASI MOTOR STEPPER ---
const bool INVERT_ALT_MOTOR = true;  
const bool INVERT_AZ_MOTOR  = true; 

float last_target_az  = -999.0;
float last_target_alt = -999.0;

#if BNO055_AVAILABLE
Adafruit_BNO055 bnoA = Adafruit_BNO055(55, 0x28, &Wire);
Adafruit_BNO055 bnoB = Adafruit_BNO055(55, 0x29, &Wire);
Adafruit_BNO055* bno = &bnoA;
bool bno_active = false;
bool calibration_loaded = false;
#endif

// --- Penyimpanan NVS untuk Kalibrasi BNO055 ---
Preferences preferences;

// --- Motor Stepper ---
#define motorAzPin1 13
#define motorAzPin2 12
#define motorAzPin3 14
#define motorAzPin4 27
AccelStepper stepperAzimuth(AccelStepper::HALF4WIRE, motorAzPin1, motorAzPin3, motorAzPin2, motorAzPin4);

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

const float STEPS_PER_DEGREE = 4096.0 / 360.0; 

// Prototipe Fungsi
void processGPS();
void parseNMEALine(String line);
float convertDegMinToDec(String degMin, char dir);
void readSensor();
void sendTelemetry();
void setTargetPosition(float target_az, float target_alt);
void handleIncomingCommand(const char* payload);
void saveCalibrationOffsets();
void clearCalibrationOffsets();
void connectMQTT();
void mqttCallback(char* topic, byte* payload, unsigned int length);

// ==========================================
// 3. FUNGSI SETUP
// ==========================================
void setup() {
    Serial.begin(115200);
    delay(1000);
    Serial.println("\n==========================================");
    Serial.println("  HILTRON ESP32 TRACKER (EMQX CLOUD MQTT)");
    Serial.println("==========================================");

    // --- 3.1 Setup GPS ---
    Serial.println("[Hardware] Inisialisasi GPS (UART2 RX=16, TX=17, 9600 baud)...");
    SerialGPS.begin(9600, SERIAL_8N1, GPS_RX_PIN, GPS_TX_PIN);

    // --- 3.2 Setup Motor Stepper ---
    Serial.println("[Hardware] Inisialisasi Motor Stepper...");
    stepperAzimuth.setMaxSpeed(1000.0);
    stepperAzimuth.setAcceleration(300.0);
    stepperAltitude.setMaxSpeed(1000.0);
    stepperAltitude.setAcceleration(300.0);

    // --- 3.3 Setup BNO055 & Load Kalibrasi Tersimpan ---
#if BNO055_AVAILABLE
    Serial.println("[Hardware] Inisialisasi Sensor Orientasi BNO055...");
    Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
    Wire.setClock(100000);
    delay(100);

    if (bnoA.begin()) {
        bno = &bnoA;
        bno_active = true;
        Serial.println("[Hardware] BNO055 Terdeteksi pada alamat 0x28.");
    } else if (bnoB.begin()) {
        bno = &bnoB;
        bno_active = true;
        Serial.println("[Hardware] BNO055 Terdeteksi pada alamat 0x29.");
    } else {
        Serial.println("[ERROR] BNO055 TIDAK TERDETEKSI!");
        bno_active = false;
    }

    if (bno_active && bno != nullptr) {
        bno->setExtCrystalUse(true);
        delay(100);

        // BACA DATA KALIBRASI DARI FLASH NVS
        preferences.begin("bno055", true);
        bool hasSavedCalib = preferences.getBool("valid", false);

        if (hasSavedCalib) {
            adafruit_bno055_offsets_t calibData;
            preferences.getBytes("calib", &calibData, sizeof(adafruit_bno055_offsets_t));
            bno->setSensorOffsets(calibData);
            calibration_loaded = true;
            Serial.println("[BNO055] >> SUKSES: Profil Kalibrasi Tersimpan Ditemukan & DIKUNCI!");
        } else {
            Serial.println("[BNO055] >> INFO: Belum ada data kalibrasi tersimpan di NVS.");
        }
        preferences.end();
        readSensor();
    }
#endif

    // --- 3.4 Setup Wi-Fi ---
    Serial.print("\nMenghubungkan ke WiFi: ");
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
        Serial.print("IP Address ESP32: ");
        Serial.println(WiFi.localIP());
    } else {
        Serial.println("\n[ERROR] WiFi Gagal Terhubung! Periksa Hotspot Anda.");
    }

    // --- 3.5 Setup MQTT EMQX ---
    mqttClient.setServer(mqtt_server, mqtt_port);
    mqttClient.setCallback(mqttCallback);
    mqttClient.setBufferSize(512); // Buffer untuk JSON telemetri

    connectMQTT();
    Serial.println("\n[Sistem] HILTRON ESP32 Siap! Menunggu instruksi...");
}

// ==========================================
// 4. MAIN LOOP (Non-Blocking)
// ==========================================
void loop() {
    // Jalankan pergerakan stepper motor setiap siklus
    stepperAzimuth.run();
    stepperAltitude.run();

    // Pastikan koneksi MQTT tetap aktif
    if (WiFi.status() == WL_CONNECTED) {
        if (!mqttClient.connected()) {
            unsigned long now = millis();
            if (now - lastMqttReconnect > 5000) {
                lastMqttReconnect = now;
                connectMQTT();
            }
        } else {
            mqttClient.loop();
        }
    }

    // Baca NMEA dari GPS
    processGPS();

    // Membaca posisi tiap 100ms
    unsigned long currentMillis = millis();
    if (currentMillis - lastSensorRead >= 100) {
        lastSensorRead = currentMillis;
        readSensor();

#if BNO055_AVAILABLE
        // Auto-save kalibrasi jika belum tersimpan dan mencapai skor memadai (Mag 3, Gyro 3, Accel >= 2)
        if (!calibration_loaded && bno_active && bno != nullptr) {
            uint8_t sys, gyro, accel, mag;
            bno->getCalibration(&sys, &gyro, &accel, &mag);
            if (mag >= 3 && gyro >= 3 && accel >= 2) {
                Serial.println("\n[BNO055] >>> Sensor Terkalibrasi Memadai! Menyimpan ke NVS... <<<");
                saveCalibrationOffsets();
            }
        }
#endif
    }

    // Kirim telemetri ke Cloud MQTT tiap 1 detik
    if (currentMillis - lastTelemetrySend >= 1000) {
        lastTelemetrySend = currentMillis;
        sendTelemetry();
    }
}

// ==========================================
// 5. MANAJEMEN KONEKSI MQTT
// ==========================================
void connectMQTT() {
    if (mqttClient.connected()) return;

    Serial.print("[MQTT] Menghubungkan ke Broker EMQX (broker.emqx.io)... ");
    String clientId = "hiltron_esp32_" + WiFi.macAddress();
    clientId.replace(":", "");

    // Connect dengan Last Will and Testament (LWT)
    if (mqttClient.connect(clientId.c_str(), topic_status, 1, true, "offline")) {
        Serial.println("TERHUBUNG!");
        mqttClient.publish(topic_status, "online", true);
        mqttClient.subscribe(topic_command);
        Serial.printf("[MQTT] Berlangganan topik perintah: %s\n", topic_command);
    } else {
        Serial.print("Gagal, rc=");
        Serial.println(mqttClient.state());
    }
}

void mqttCallback(char* topic, byte* payload, unsigned int length) {
    char message[length + 1];
    memcpy(message, payload, length);
    message[length] = '\0';

    Serial.printf("\n[MQTT] Pesan Masuk [%s]: %s\n", topic, message);
    handleIncomingCommand(message);
}

// ==========================================
// 6. PENANGAN PERINTAH TELESKOP
// ==========================================
void handleIncomingCommand(const char* payload) {
    StaticJsonDocument<256> doc;
    DeserializationError error = deserializeJson(doc, payload);

    if (error) {
        Serial.print("JSON Error: ");
        Serial.println(error.f_str());
        return;
    }

    const char* command = doc["command"];
    if (!command) return;

    // Arahkan Hilal
    if (strcmp(command, "POINT_HILAL") == 0) {
        float target_azimuth = doc["target_azimuth"];
        float target_altitude = doc["target_altitude"];

        Serial.println("\n>>> PERINTAH ARAHKAN HILAL DITERIMA <<<");
        Serial.printf("Target Azimuth  : %.2f°\n", target_azimuth);
        Serial.printf("Target Altitude : %.2f°\n", target_altitude);

        setTargetPosition(target_azimuth, target_altitude);
    }
    // Kalibrasi Titik Nol (Set Home)
    else if (strcmp(command, "SET_HOME") == 0) {
        Serial.println("\n[Motor] Menetapkan posisi fisik saat ini sebagai Titik Nol (0° Hadap Utara & 0° Ufuk)...");
        stepperAltitude.setCurrentPosition(0);
        stepperAzimuth.setCurrentPosition(0);
        last_target_az  = -999.0;
        last_target_alt = -999.0;
        current_azimuth  = 0.0;
        current_altitude = 0.0;
        sendTelemetry();
    }
    // Simpan Kalibrasi BNO055
    else if (strcmp(command, "SAVE_CALIBRATION") == 0) {
        Serial.println("[MQTT] Menerima instruksi simpan kalibrasi...");
        saveCalibrationOffsets();
    }
    // Reset Kalibrasi BNO055
    else if (strcmp(command, "CLEAR_CALIBRATION") == 0) {
        Serial.println("[MQTT] Menerima instruksi reset kalibrasi...");
        clearCalibrationOffsets();
    }
}

// ==========================================
// 7. LOGIKA PERGERAKAN MOTOR
// ==========================================
void setTargetPosition(float target_az, float target_alt) {
    float safe_alt = target_alt;
    if (safe_alt < 0.0)  safe_alt = 0.0;
    if (safe_alt > 90.0) safe_alt = 90.0;

    if (abs(target_az - last_target_az) < 0.1 && abs(safe_alt - last_target_alt) < 0.1) {
        Serial.println("[Motor] Target sudah tercapai (posisi sama). Motor mengunci.");
        return;
    }

    float norm_az = target_az;
    while (norm_az < 0.0)    norm_az += 360.0;
    while (norm_az >= 360.0) norm_az -= 360.0;

    float azFromNorth = norm_az;
    if (azFromNorth > 180.0) azFromNorth -= 360.0;

    long targetStepAzimuth  = (long)(azFromNorth * STEPS_PER_DEGREE) * (INVERT_AZ_MOTOR ? -1 : 1);
    long targetStepAltitude = (long)(safe_alt * STEPS_PER_DEGREE) * (INVERT_ALT_MOTOR ? -1 : 1);

    Serial.printf("  Target Az: %.2f° (Relatif Utara: %.2f°, Step: %ld)\n", norm_az, azFromNorth, targetStepAzimuth);
    Serial.printf("  Target Alt: %.2f° (Step: %ld)\n", safe_alt, targetStepAltitude);

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
    if (!mqttClient.connected()) return;

    uint8_t system = 0, gyro = 0, accel = 0, mag = 0;
#if BNO055_AVAILABLE
    if (bno_active && bno != nullptr) {
        bno->getCalibration(&system, &gyro, &accel, &mag);
        if (calibration_loaded) {
            system = 3; gyro = 3; accel = 3; mag = 3;
        }
    }
#endif

    char telemetry[340];
    sprintf(telemetry, 
        "{\"type\":\"telemetry\",\"azimuth\":%.2f,\"altitude\":%.2f,\"cal_sys\":%d,\"cal_gyro\":%d,\"cal_accel\":%d,\"cal_mag\":%d,\"cal_locked\":%s,\"gps_valid\":%s,\"gps_lat\":%.6f,\"gps_lon\":%.6f,\"gps_sats\":%d}",
        current_azimuth, current_altitude, system, gyro, accel, mag,
        calibration_loaded ? "true" : "false",
        gps_valid ? "true" : "false", gps_lat, gps_lon, gps_sats
    );

    mqttClient.publish(topic_telemetry, telemetry);
}

// ==========================================
// 8. MANAJEMEN KALIBRASI BNO055 (NVS FLASH)
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
        } else {
            Serial.println("[BNO055] Gagal mengambil sensor offsets dari chip.");
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
    Serial.println("[BNO055] Data kalibrasi di NVS berhasil di-reset / dihapus!");
    sendTelemetry();
#endif
}

// ==========================================
// 9. PARSER NMEA GPS
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

