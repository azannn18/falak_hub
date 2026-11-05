#include <WiFi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BNO055.h>
#include <AccelStepper.h>
#include <HardwareSerial.h>
#include <Preferences.h>

// ==========================================
// 1. KONFIGURASI JARINGAN & SERVER
// ==========================================   
const char* ssid     = "HILTRON";          // Sesuai nama Mobile Hotspot di laptop Anda
const char* password = "12345678";         // Password Hotspot

// --- PENGATURAN MODE SERVER (LOKAL vs CLOUD RENDER/RAILWAY) ---
// Set USE_CLOUD_WSS = true jika terhubung ke server online (Render / Railway WSS port 443)
// Set USE_CLOUD_WSS = false jika terhubung ke laptop lokal (Hotspot / WiFi port 8000)
const bool USE_CLOUD_WSS = false; 

// Konfigurasi jika LOKAL:
const char* local_server = "192.168.137.1"; 
const uint16_t local_port = 8000;

// Konfigurasi jika CLOUD (ganti dengan domain Render Anda, contoh: "hiltron.onrender.com" tanpa https://):
const char* cloud_server = "hiltron.onrender.com";
const uint16_t cloud_port = 443;

const char* websocket_path   = "/ws/esp32";     

WebSocketsClient webSocket;

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

// Pin I2C ESP32 untuk BNO055 (default: SDA = GPIO 21, SCL = GPIO 22)
#define I2C_SDA_PIN 21
#define I2C_SCL_PIN 22

// Penyesuaian / Offset Orientasi Fisik Sensor (jika diperlukan)
const float AZIMUTH_OFFSET  = 0.0;   // Offset sudut Azimuth (+/- derajat)
const float ALTITUDE_OFFSET = 0.0;   // Offset sudut Altitude (+/- derajat elevasi)
const bool  INVERT_ALTITUDE = false; // Set ke true jika arah elevasi sensor terbalik saat mendongak

// --- KONFIGURASI ARAH PUTARAN MOTOR STEPPER ---
// INVERT_ALT_MOTOR = true agar nilai altitude positif (mendongak ke langit) memutar motor ke atas, bukan ke meja.
const bool INVERT_ALT_MOTOR = true;  
// INVERT_AZ_MOTOR = true agar target sudut arah Barat berputar ke KIRI (Counter-Clockwise) dari posisi awal Hadap Utara.
const bool INVERT_AZ_MOTOR  = true; 

// Penyimpanan target terakhir untuk mencegah pergerakan berulang saat tombol ditekan berkali-kali
float last_target_az  = -999.0;
float last_target_alt = -999.0;

#if BNO055_AVAILABLE
Adafruit_BNO055 bnoA = Adafruit_BNO055(55, 0x28, &Wire);
Adafruit_BNO055 bnoB = Adafruit_BNO055(55, 0x29, &Wire);
Adafruit_BNO055* bno = &bnoA;
bool bno_active = false;
bool calibration_loaded = false; // Status apakah profil kalibrasi tersimpan sudah aktif
#endif

// --- Penyimpanan Non-Volatile (NVS) untuk Kalibrasi BNO055 ---
Preferences preferences;

// --- Motor Stepper ---
// Motor 1 — Azimuth (Horizontal): IN1=13, IN2=12, IN3=14, IN4=27
#define motorAzPin1 13
#define motorAzPin2 12
#define motorAzPin3 14
#define motorAzPin4 27
AccelStepper stepperAzimuth(AccelStepper::HALF4WIRE, motorAzPin1, motorAzPin3, motorAzPin2, motorAzPin4);

// Motor 2 — Altitude (Vertikal): IN1=26, IN2=25, IN3=33, IN4=32
#define motorAltPin1 26
#define motorAltPin2 25
#define motorAltPin3 33
#define motorAltPin4 32
AccelStepper stepperAltitude(AccelStepper::HALF4WIRE, motorAltPin1, motorAltPin3, motorAltPin2, motorAltPin4);

// Variabel posisi motor
float current_azimuth  = 0.0;
float current_altitude = 0.0;
unsigned long lastSensorRead    = 0;
unsigned long lastTelemetrySend = 0;

// 1 Derajat = 4096 / 360 = ~11.377 step (Motor 28BYJ-48 HALF4WIRE)
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

// ==========================================
// 3. FUNGSI SETUP
// ==========================================
void setup() {
    Serial.begin(115200);
    delay(1000);
    
    // --- 3.1 Setup GPS ---
    Serial.println("\n[Hardware] Inisialisasi GPS (UART2 RX=16, TX=17, 9600 baud)...");
    SerialGPS.begin(9600, SERIAL_8N1, GPS_RX_PIN, GPS_TX_PIN);

    // --- 3.2 Setup Motor Stepper ---
    Serial.println("[Hardware] Inisialisasi Motor Stepper...");
    stepperAzimuth.setMaxSpeed(1000.0);
    stepperAzimuth.setAcceleration(300.0); // Percepatan agar putaran halus
    
    stepperAltitude.setMaxSpeed(1000.0);
    stepperAltitude.setAcceleration(300.0);

    // --- 3.3 Setup BNO055 & Load Kalibrasi Tersimpan ---
#if BNO055_AVAILABLE
    Serial.println("[Hardware] Inisialisasi Sensor Orientasi BNO055...");
    Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
    Wire.setClock(100000); // 100 kHz I2C clock (sangat direkomendasikan untuk stabilitas BNO055)
    delay(100);

    // Coba deteksi alamat 0x28 (default) terlebih dahulu
    if (bnoA.begin()) {
        bno = &bnoA;
        bno_active = true;
        Serial.println("[Hardware] BNO055 BERHASIL Terdeteksi pada alamat 0x28 (BNO055_ADDRESS_A).");
    } 
    // Jika tidak ditemukan di 0x28, coba alamat alternatif 0x29
    else if (bnoB.begin()) {
        bno = &bnoB;
        bno_active = true;
        Serial.println("[Hardware] BNO055 BERHASIL Terdeteksi pada alamat 0x29 (BNO055_ADDRESS_B).");
    } 
    else {
        Serial.println("[ERROR] BNO055 TIDAK TERDETEKSI pada alamat 0x28 maupun 0x29!");
        Serial.println("  >> Periksa koneksi kabel jumper I2C (SDA=21, SCL=22, VIN=3.3V/5V, GND=GND).");
        bno_active = false;
    }

    if (bno_active && bno != nullptr) {
        bno->setExtCrystalUse(true);
        Serial.println("[Hardware] BNO055: External Crystal Oscillator 32.768 kHz diaktifkan.");
        delay(100);

        // --- BACA DATA KALIBRASI DARI FLASH NVS ESP32 ---
        preferences.begin("bno055", true); // Buka mode read-only
        bool hasSavedCalib = preferences.getBool("valid", false);

        if (hasSavedCalib) {
            adafruit_bno055_offsets_t calibData;
            preferences.getBytes("calib", &calibData, sizeof(adafruit_bno055_offsets_t));
            bno->setSensorOffsets(calibData);
            calibration_loaded = true;
            Serial.println("[BNO055] >> SUKSES: Profil Kalibrasi Tersimpan Ditemukan & DIKUNCI!");
            Serial.printf("[BNO055] >> Accel Radius: %d, Mag Radius: %d\n", calibData.accel_radius, calibData.mag_radius);
        } else {
            Serial.println("[BNO055] >> INFO: Belum ada data kalibrasi tersimpan di NVS.");
            Serial.println("[BNO055] >> Lakukan kalibrasi gerakan (angka 8). Sistem akan otomatis menyimpannya saat skor 3/3/3/3 tercapai.");
        }
        preferences.end();

        readSensor();
        Serial.printf("[Hardware] Orientasi Awal Sensor: Azimuth=%.2f°, Altitude=%.2f°\n", current_azimuth, current_altitude);
    }
#else
    Serial.println("[Hardware] BNO055 DINONAKTIFKAN (Mode Open-Loop Aktif).");
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
        Serial.println("\n[ERROR] WiFi Gagal Terhubung!");
    }

    // --- 3.5 Setup WebSocket ---
    if (USE_CLOUD_WSS) {
        Serial.printf("[WS] Menghubungkan ke Server Cloud (WSS SSL 443): wss://%s:%d%s\n", cloud_server, cloud_port, websocket_path);
        webSocket.beginSSL(cloud_server, cloud_port, websocket_path);
    } else {
        Serial.printf("[WS] Menghubungkan ke Server Lokal: ws://%s:%d%s\n", local_server, local_port, websocket_path);
        webSocket.begin(local_server, local_port, websocket_path);
    }
    webSocket.onEvent(webSocketEvent);
    webSocket.setReconnectInterval(5000);
    
    Serial.println("\n[Sistem] HILTRON ESP32 Siap! Menunggu instruksi...");
}

// ==========================================
// 4. FUNGSI MAIN LOOP (Non-Blocking)
// ==========================================
void loop() {
    webSocket.loop(); 
    
    // Gerakkan motor jika ada target posisi aktif
    stepperAzimuth.run();
    stepperAltitude.run();

    // Baca data aliran NMEA dari modul GPS terus-menerus
    processGPS();

    // Membaca posisi tiap 100ms
    unsigned long currentMillis = millis();
    if (currentMillis - lastSensorRead >= 100) {
        lastSensorRead = currentMillis;
        readSensor();

#if BNO055_AVAILABLE
        // Auto-save kalibrasi pertama kali jika belum tersimpan dan sensor mencapai kualitas yang memadai
        // Syarat praktis: Magnetometer & Gyroscope 3 (sempurna), Accelerometer minimal 2 (stabil)
        if (!calibration_loaded && bno_active && bno != nullptr) {
            uint8_t sys, gyro, accel, mag;
            bno->getCalibration(&sys, &gyro, &accel, &mag);
            if (mag >= 3 && gyro >= 3 && accel >= 2) {
                Serial.println("\n[BNO055] >>> Sensor Terkalibrasi Memadai (Mag=3, Gyro=3, Accel>=2)! Otomatis Mengunci & Menyimpan ke NVS... <<<");
                saveCalibrationOffsets();
            }
        }
#endif
    }

    // Kirim telemetri (Orientasi + Kalibrasi + GPS) ke server tiap 1 detik
    if (currentMillis - lastTelemetrySend >= 1000) {
        lastTelemetrySend = currentMillis;
        sendTelemetry();
    }
}

// ==========================================
// 5. PARSER NMEA GPS
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
                nmeaSentence = ""; // Reset jika buffer overflow
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
            if (status == "A") { // 'A' = Valid fix
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
// 6. MANAJEMEN KALIBRASI BNO055 (NVS FLASH)
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
            if (webSocket.isConnected()) {
                webSocket.sendTXT("{\"type\":\"event\",\"status\":\"CALIBRATION_SAVED\"}");
            }
            sendTelemetry(); // Update status terkunci seketika ke dashboard
        } else {
            Serial.println("[BNO055] Gagal mengambil sensor offsets dari chip.");
            if (webSocket.isConnected()) {
                webSocket.sendTXT("{\"type\":\"event\",\"status\":\"CALIBRATION_FAILED\"}");
            }
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
    if (webSocket.isConnected()) {
        webSocket.sendTXT("{\"type\":\"event\",\"status\":\"CALIBRATION_CLEARED\"}");
    }
    sendTelemetry(); // Update status reset seketika ke dashboard
#endif
}

// ==========================================
// 7. CALLBACK WEBSOCKET (PENERIMA PESAN)
// ==========================================
void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
    switch(type) {
        case WStype_DISCONNECTED:
            Serial.println("[WS] Terputus dari Server!");
            break;
            
        case WStype_CONNECTED:
            Serial.printf("[WS] Terhubung ke Server URL: %s\n", payload);
            webSocket.sendTXT("{\"status\": \"ESP32_READY\"}");
            break;
            
        case WStype_TEXT:
            handleIncomingCommand((char*)payload);
            break;
    }
}

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
    
    // Perintah Gerakkan Tracker ke Posisi Hilal
    if (strcmp(command, "POINT_HILAL") == 0) {
        float target_azimuth = doc["target_azimuth"];
        float target_altitude = doc["target_altitude"];
        
        Serial.println("\n>>> PERINTAH ARAHKAN HILAL DITERIMA <<<");
        Serial.printf("Target Azimuth  : %.2f\n", target_azimuth);
        Serial.printf("Target Altitude : %.2f\n", target_altitude);
        
        setTargetPosition(target_azimuth, target_altitude);
    }
    // Perintah Manual Simpan Kalibrasi BNO055
    else if (strcmp(command, "SAVE_CALIBRATION") == 0) {
        Serial.println("[WS] Menerima instruksi simpan kalibrasi...");
        saveCalibrationOffsets();
    }
    // Perintah Reset / Hapus Kalibrasi di NVS (jika ingin kalibrasi ulang dari nol)
    else if (strcmp(command, "CLEAR_CALIBRATION") == 0) {
        Serial.println("[WS] Menerima instruksi reset kalibrasi...");
        clearCalibrationOffsets();
    }
    // Perintah Kalibrasi Titik Nol (Set Home): Tetapkan posisi fisik saat ini = Hadap Utara (0°) & Ufuk Datar (0°)
    else if (strcmp(command, "SET_HOME") == 0) {
        Serial.println("\n[Motor] Menetapkan posisi fisik saat ini sebagai Titik Nol (Home: Hadap Utara & Ufuk 0°)...");
        stepperAltitude.setCurrentPosition(0);
        stepperAzimuth.setCurrentPosition(0);
        last_target_az  = -999.0;
        last_target_alt = -999.0;
        current_azimuth  = 0.0;
        current_altitude = 0.0;
        if (webSocket.isConnected()) {
            webSocket.sendTXT("{\"type\":\"event\",\"status\":\"HOME_SET\"}");
        }
    }
}

// ==========================================
// 8. LOGIKA PERGERAKAN MOTOR
// ==========================================
void setTargetPosition(float target_az, float target_alt) {
    // 1. Proteksi batas fisik altitude (0° s/d 90°):
    // Jika hilal berada di bawah ufuk, jangan biarkan motor menunduk menabrak meja! Kunci di posisi 0.0°
    float safe_alt = target_alt;
    if (safe_alt < 0.0)  safe_alt = 0.0;
    if (safe_alt > 90.0) safe_alt = 90.0; // Maksimal tegak lurus langit (Zenith)

    // 2. Cegah pergerakan berulang jika target masih sama persis (IDEMPOTENT):
    if (abs(target_az - last_target_az) < 0.1 && abs(safe_alt - last_target_alt) < 0.1) {
        Serial.println("[Motor] Target sudah tercapai (posisi sama). Motor mengunci dan tidak bergerak.");
        return;
    }

    // 3. Perhitungan Posisi Absolut Azimuth terhadap Titik Nol (0° = Utara):
    float norm_az = target_az;
    while (norm_az < 0.0)    norm_az += 360.0;
    while (norm_az >= 360.0) norm_az -= 360.0;

    // Rute putaran terpendek -180° s/d +180° dari Titik Nol Hadap Utara:
    // Contoh: Barat (285°) -> 285 - 360 = -75° (putar 75° ke KIRI).
    // Contoh: Timur (75°) -> +75° (putar 75° ke KANAN).
    float azFromNorth = norm_az;
    if (azFromNorth > 180.0) azFromNorth -= 360.0;

    long targetStepAzimuth  = (long)(azFromNorth * STEPS_PER_DEGREE) * (INVERT_AZ_MOTOR ? -1 : 1);
    long targetStepAltitude = (long)(safe_alt * STEPS_PER_DEGREE) * (INVERT_ALT_MOTOR ? -1 : 1);

    Serial.println("\n>>> INSTRUKSI TARGET HILAL BARU DITERIMA <<<");
    Serial.printf("  Target Azimuth  : %.2f° (Relatif Utara: %.2f°, Putar: %s, Step: %ld)\n", 
                  norm_az, azFromNorth, (azFromNorth < 0 ? "KIRI (Barat)" : "KANAN (Timur)"), targetStepAzimuth);
    Serial.printf("  Target Altitude : %.2f° (Safe Alt: %.2f°, Step: %ld)\n", target_alt, safe_alt, targetStepAltitude);

    // Gerakkan motor secara ABSOLUT ke target langkah yang dihitung dari Titik Nol (Home)
    stepperAzimuth.moveTo(targetStepAzimuth);
    stepperAltitude.moveTo(targetStepAltitude);

    // Simpan target aktif untuk mencegah pergerakan duplikat
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

    // Update posisi sudut teleskop real-time dari hitungan langkah motor stepper yang presisi
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
        // Jika profil kalibrasi dari Flash NVS/EEPROM aktif, laporkan status optimal 3/3/3/3
        if (calibration_loaded) {
            system = 3;
            gyro   = 3;
            accel  = 3;
            mag    = 3;
        }
    }
#endif

    // Kirim paket telemetri lengkap: Orientasi + Status Kalibrasi + Status GPS + Koordinat
    char telemetry[340];
    sprintf(telemetry, 
        "{\"type\":\"telemetry\",\"azimuth\":%.2f,\"altitude\":%.2f,\"cal_sys\":%d,\"cal_gyro\":%d,\"cal_accel\":%d,\"cal_mag\":%d,\"cal_locked\":%s,\"gps_valid\":%s,\"gps_lat\":%.6f,\"gps_lon\":%.6f,\"gps_sats\":%d}",
        current_azimuth, current_altitude, system, gyro, accel, mag,
        calibration_loaded ? "true" : "false",
        gps_valid ? "true" : "false", gps_lat, gps_lon, gps_sats
    );
    webSocket.sendTXT(telemetry);
}
