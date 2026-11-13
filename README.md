# HILTRON — Islamic Astronomical Observatory & Autonomous Hilal Tracker

> **Sistem Observatorium Astronomi Islam Berbasis Ephemeris NASA JPL DE421, Visualisasi 3D Interaktif (Three.js), dan Pelacak Hilal Otomatis Berbasis Mikrokontroler IoT (ESP32).**

Untuk ringkasan teknis dan arsitektur lengkap, silakan baca dokumentasi utama di:
📄 **[project_summary.md](file:///d:/coding/FalakHub/project_summary.md)**

---

## Ringkasan Singkat

**HILTRON** adalah platform observatorium digital terintegrasi yang menggabungkan kalkulasi astronomi Islam (*ilmu falak*) berpresisi tinggi dengan teknologi visualisasi 3D modern serta perangkat keras pelacak (*tracker*) teleskop otomatis.

### Fitur Utama
1. **Presisi Ephemeris NASA JPL DE421**: Perhitungan posisi astronomis matahari, bulan, waktu sunset, GMST, dan konversi kalender Hijriah (Umm al-Qura) via Python Skyfield.
2. **Kriteria MABIMS 2021 & Wujudul Hilal**: Evaluasi otomatis kriteria keterlihatan hilal (Tinggi Hilal $\ge 3^\circ$, Elongasi $\ge 6.4^\circ$).
3. **Peta Visibilitas Global (Big Data Spatial)**: Grid global sebaran keterlihatan hilal dunia yang di-serialize dengan format biner **Geobuf / Protocol Buffers**.
4. **Visualisasi 3D Interaktif Ganda**:
   * **Earth Globe 3D**: Bola bumi fotorealistik (Three.js) dengan tekstur NASA, pendaran atmosfer luar angkasa, pencahayaan matahari (*lensflare* prosedural), dan posisi bulan.
   * **Skydome Horizon 3D**: Simulasi ufuk barat dengan *Custom GLSL Sky Shader* (hamburan Rayleigh, golden hour, langit malam, dan fase bulan).
5. **Autonomous Hardware Tracker & Celestial Live Lock Tracking (ESP32 IoT)**:
   * Pengendali teleskop sumbu ganda (*Azimuth & Altitude*) menggunakan motor stepper 28BYJ-48 via `AccelStepper`.
   * **Celestial Live Lock Tracking**: Pelacakan kontinu pergerakan hilal secara *real-time* berbasis ephemeris JPL dengan *micro-stepping* otomatis (~14.5°/jam) untuk mengimbangi rotasi bumi.
   * Algoritma *Shortest Path Angle Wrapping* ($-180^\circ \dots +180^\circ$).
   * Modul GPS NEO-6M (NMEA parser pada UART2) dan sensor orientasi 9-DOF Bosch BNO055 (tersimpan permanen di NVS Flash).
   * Dual-Protocols: Komunikasi WebSocket bi-directional (`/ws/esp32`) dan EMQX Cloud MQTT (`hiltron/tracker/*`).

---

## Struktur Folder

```text
FalakHub/
├── backend/
│   ├── ai/
│   │   └── predictive_cache.py     # Generator & caching spatial grid global (Geobuf / Protocol Buffers)
│   ├── astronomy/
│   │   └── engine.py               # Mesin hisab: Skyfield, DE421, kriteria MABIMS, Hijri date
│   ├── de421.bsp                   # Binary NASA JPL Spice Kernel (Posisi Bumi, Bulan, Matahari)
│   ├── main.py                     # Entry point FastAPI, route REST, WebSocket handler, & static mount
│   └── requirements.txt            # Dependensi Python
├── firmware/
│   └── esp32_tracker/
│       ├── esp32_tracker.ino       # Firmware C++/Arduino ESP32 (WebSocket Edition)
│       └── esp32_tracker_mqtt.ino  # Firmware C++/Arduino ESP32 (Cloud MQTT Edition via EMQX)
├── frontend/
│   ├── css/
│   │   ├── landing.css             # Desain styling landing page HILTRON
│   │   ├── style.css               # Desain glassmorphism & HUD styling observatorium
│   │   └── tailwind.css            # Bundle utilitas Tailwind CSS
│   ├── js/
│   │   ├── api.js                  # Panggilan API backend & Geobuf decoder
│   │   ├── globe.js                # Render 3D Earth, orbit, lensflare, & marker
│   │   ├── main.js                 # State manager aplikasi, UI logic, GPS, & telemetri
│   │   ├── skydome.js              # Render 3D Skydome horizon & custom GLSL 24h shader
│   │   └── tailwind-config.js      # Konfigurasi Tailwind CSS
│   ├── index.html                  # Landing page interaktif HILTRON (Showcase, fitur, download)
│   └── app.html                    # Web HUD & Observatorium 3D interaktif utama
├── vercel.json                     # Konfigurasi deployment serverless Vercel
├── project_summary.md              # Dokumentasi arsitektur komprehensif
└── README.md                       # Ringkasan cepat proyek
```

---

## Panduan Menjalankan Cepat (Quick Start)

### 1. Jalankan Backend
```bash
# Buat dan aktifkan venv
python -m venv .venv
.\.venv\Scripts\Activate.ps1    # Di Windows PowerShell

# Instal dependensi
pip install -r backend/requirements.txt

# Jalankan server
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Akses Aplikasi
Buka browser pada alamat:
```text
http://localhost:8000
```
Swagger API docs: `http://localhost:8000/docs`

---
*Dokumentasi lengkap dapat dipelajari di [project_summary.md](file:///d:/coding/FalakHub/project_summary.md).*
