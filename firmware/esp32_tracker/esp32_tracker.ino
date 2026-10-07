#include <WiFi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BNO055.h>
#include <AccelStepper.h>

// ==========================================
// 1. KONFIGURASI JARINGAN & SERVER
// ==========================================
const char* ssid = "Infinix NOTE 50 Pro";           // MASUKKAN NAMA WIFI ANDA
const char* password = "kontolbaru";   // MASUKKAN PASSWORD WIFI ANDA

// Ganti dengan IP Address Komputer (tempat backend FastAPI berjalan)
const char* websocket_server = "10.230.249.223"; 
const uint16_t websocket_port = 8000;         
const char* websocket_path = "/ws/esp32";     

WebSocketsClient webSocket;

// ==========================================
// 2. OBJEK HARDWARE (BNO055 & STEPPER)
// ==========================================
// Inisialisasi Sensor BNO055
// Modul GY-BNO055 biasanya menggunakan alamat 0x29. Jika menggunakan modul asli Adafruit, gunakan 0x28.
Adafruit_BNO055 bno = Adafruit_BNO055(55, 0x29);

// Definisi Pin Motor Stepper 1 (Azimuth / Horizontal)
#define motorAzPin1 19
#define motorAzPin2 18
#define motorAzPin3 5
#define motorAzPin4 23
// Urutan pin untuk modul 28BYJ-48 dengan driver ULN2003 biasanya IN1, IN3, IN2, IN4
AccelStepper stepperAzimuth(AccelStepper::HALF4WIRE, motorAzPin1, motorAzPin3, motorAzPin2, motorAzPin4);

// Definisi Pin Motor Stepper 2 (Altitude / Vertikal) - Sesuai panduan Anda
#define motorAltPin1 26
#define motorAltPin2 25
#define motorAltPin3 33
#define motorAltPin4 32
AccelStepper stepperAltitude(AccelStepper::HALF4WIRE, motorAltPin1, motorAltPin3, motorAltPin2, motorAltPin4);

// Variabel untuk menyimpan pembacaan sensor orientasi saat ini
float current_azimuth = 0.0;
float current_altitude = 0.0;
unsigned long lastSensorRead = 0;
unsigned long lastTelemetrySend = 0;

// Konversi Derajat ke Step (Motor 28BYJ-48 mode HALF4WIRE memiliki 4096 step/revolusi)
// Jadi 1 Derajat = 4096 / 360 = 11.377 step
const float STEPS_PER_DEGREE = 4096.0 / 360.0; 

// ==========================================
// 3. FUNGSI SETUP
// ==========================================
void setup() {
    Serial.begin(115200);
    delay(1000);
    
    // --- 3.1 Setup Motor Stepper ---
    Serial.println("\n[Hardware] Inisialisasi Motor & Sensor...");
    stepperAzimuth.setMaxSpeed(1000.0);
    stepperAzimuth.setAcceleration(300.0); // Percepatan agar putaran halus
    
    stepperAltitude.setMaxSpeed(1000.0);
    stepperAltitude.setAcceleration(300.0);

    // --- 3.2 Setup BNO055 ---
    if(!bno.begin()) {
      Serial.println("[ERROR] BNO055 tidak terdeteksi! Cek kabel I2C (SDA/SCL).");
    } else {
      Serial.println("[Hardware] BNO055 Berhasil Terdeteksi.");
      bno.setExtCrystalUse(true); // Gunakan crystal eksternal BNO055 agar lebih akurat
    }

    // --- 3.3 Setup Wi-Fi ---
    Serial.print("\nMenghubungkan ke WiFi: ");
    Serial.println(ssid);
    WiFi.begin(ssid, password);
    
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println("\nWiFi Berhasil Terhubung.");
    Serial.print("IP Address ESP32: ");
    Serial.println(WiFi.localIP());

    // --- 3.4 Setup WebSocket ---
    webSocket.begin(websocket_server, websocket_port, websocket_path);
    webSocket.onEvent(webSocketEvent);
    webSocket.setReconnectInterval(5000); // Coba koneksi ulang tiap 5 detik jika putus
    
    Serial.println("\n[Sistem] FalakHub ESP32 Siap! Menunggu instruksi...");
}

// ==========================================
// 4. FUNGSI MAIN LOOP (Non-Blocking)
// ==========================================
void loop() {
    // Wajib dipanggil untuk menjaga sinyal WebSocket
    webSocket.loop(); 
    
    // Wajib dipanggil setiap saat agar motor bergerak menuju target posisi
    stepperAzimuth.run();
    stepperAltitude.run();

    // Membaca BNO055 tiap 100ms (10 kali per detik) untuk update motor
    unsigned long currentMillis = millis();
    if (currentMillis - lastSensorRead >= 100) {
        lastSensorRead = currentMillis;
        readSensor();
    }

    // Kirim telemetri ke server tiap 1 detik agar tidak memberatkan jaringan
    if (currentMillis - lastTelemetrySend >= 1000) {
        lastTelemetrySend = currentMillis;
        sendTelemetry();
    }
}

// ==========================================
// 5. CALLBACK WEBSOCKET (PENERIMA PESAN)
// ==========================================
void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
    switch(type) {
        case WStype_DISCONNECTED:
            Serial.println("[WS] Terputus dari Server!");
            break;
            
        case WStype_CONNECTED:
            Serial.printf("[WS] Terhubung ke Server URL: %s\n", payload);
            webSocket.sendTXT("{\"status\": \"ESP32_READY\"}"); // Beritahu server
            break;
            
        case WStype_TEXT:
            // Tangkap text JSON dan proses
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
    
    if (command && strcmp(command, "POINT_HILAL") == 0) {
        float target_azimuth = doc["target_azimuth"];
        float target_altitude = doc["target_altitude"];
        
        Serial.println("\n>>> PERINTAH ARAHKAN HILAL DITERIMA <<<");
        Serial.printf("Target Azimuth  : %.2f\n", target_azimuth);
        Serial.printf("Target Altitude : %.2f\n", target_altitude);
        
        setTargetPosition(target_azimuth, target_altitude);
    }
}

// ==========================================
// 6. LOGIKA PERGERAKAN (KONTROL TERTUTUP)
// ==========================================
void setTargetPosition(float target_az, float target_alt) {
    // 1. Hitung delta (jarak sudut) dari posisi hadap sekarang ke posisi target
    float deltaAzimuth = target_az - current_azimuth;
    float deltaAltitude = target_alt - current_altitude;

    // Normalisasi deltaAzimuth agar selalu menempuh rute putaran terpendek (-180 sampai 180)
    if (deltaAzimuth > 180.0)  deltaAzimuth -= 360.0;
    if (deltaAzimuth < -180.0) deltaAzimuth += 360.0;

    // 2. Ubah Jarak Sudut (Derajat) menjadi Jumlah Step Motor
    long stepsToMoveAzimuth = deltaAzimuth * STEPS_PER_DEGREE;
    long stepsToMoveAltitude = deltaAltitude * STEPS_PER_DEGREE;

    Serial.printf("[Motor] Berputar %ld langkah Azimuth, %ld langkah Altitude\n", stepsToMoveAzimuth, stepsToMoveAltitude);

    // 3. Perintahkan AccelStepper bergerak ke target ABSOLUT dari posisi saat ini.
    // Jika tombol ditekan berulang-ulang, target tidak akan menumpuk (bertambah terus).
    stepperAzimuth.moveTo(stepperAzimuth.currentPosition() + stepsToMoveAzimuth);
    stepperAltitude.moveTo(stepperAltitude.currentPosition() + stepsToMoveAltitude);
}

void readSensor() {
    sensors_event_t event;
    bno.getEvent(&event);
    
    // Baca posisi absolut teleskop saat ini
    // event.orientation.x adalah arah kompas (Heading/Azimuth, 0-360 derajat)
    // event.orientation.y atau z adalah kemiringan (Pitch/Roll), tergantung orientasi modul saat dipasang
    current_azimuth = event.orientation.x; 
    current_altitude = event.orientation.y; 
    current_azimuth = event.orientation.x; 
    current_altitude = event.orientation.y; 
}

void sendTelemetry() {
    // Baca status kalibrasi (0 = Buruk/Belum, 3 = Sangat Baik)
    uint8_t system, gyro, accel, mag = 0;
    bno.getCalibration(&system, &gyro, &accel, &mag);
    
    // Kirim data telemetri ke server
    char telemetry[200];
    sprintf(telemetry, "{\"type\":\"telemetry\",\"azimuth\":%.2f,\"altitude\":%.2f,\"cal_sys\":%d,\"cal_gyro\":%d,\"cal_accel\":%d,\"cal_mag\":%d}", 
            current_azimuth, current_altitude, system, gyro, accel, mag);
    webSocket.sendTXT(telemetry);
}
