import { initGlobe }   from './globe.js';
import { initSkydome }  from './skydome.js';
import { fetchEphemeris, fetchMabimsMap, fetchGeocode, fetchTelemetry } from './api.js';
import { initMqttBridge, sendMqttCommand, isMqttConnected } from './mqtt-bridge.js';

/* ═══════════════════════════════════════════════════════════════
   HILTRON · main.js
   Unified state manager. Drives both the 3D Globe and Skydome
   from a single source of truth: real ephemeris data from the
   FastAPI/Skyfield backend.
═══════════════════════════════════════════════════════════════ */

// ── App State ─────────────────────────────────────────────────
let appState = {
    activeCityIdx:     0,
    timeOffsetMinutes: 0,
    date:              new Date().toISOString().split('T')[0],

    // Active location
    lat:  -6.2088,
    lon:  106.8456,

    // Latest backend response values
    baseTime:     new Date(),
    baseSunAlt:   -10,
    baseSunAz:    270,
    baseSunRa:    0,
    baseSunDec:   0,
    baseMoonAlt:   5,
    baseMoonAz:   285,
    baseMoonRa:   0,
    baseMoonDec:  0,
    baseArcl:      0,
    baseArcv:      0,
    baseGMST:      0,
    status:        '',
    illumination:  0,
};

// ── Dynamic Simulation Engine State ───────────────────────────
let simState = {
    isRunning: true,
    speedMultiplier: 1, // 1x = waktu nyata (real-time), 10x, 60x
    lastTickMs: Date.now(),
    simulatedElapsedSeconds: 0,
    lastAutoSyncTime: Date.now(),
};

// ── City Registry (dynamic — unlimited) ───────────────────────
const CITIES = [
    { name: 'Jakarta, Indonesia',    lat: -6.2088,  lon: 106.8456 },
    { name: 'Makkah al-Mukarramah', lat: 21.4225,  lon:  39.8262 },
    { name: 'Kuala Lumpur, MY',      lat:  3.1390,  lon: 101.6869 },
    { name: 'Istanbul, Turkey',      lat: 41.0082,  lon:  28.9784 },
    { name: 'Cairo, Egypt',          lat: 30.0444,  lon:  31.2357 },
    { name: 'Greenwich, UK',         lat: 51.4826,  lon:  -0.0077 },
    { name: 'Tokyo, Japan',          lat: 35.6762,  lon: 139.6503 },
];

let globe, skydome;

// ── DOM Helpers ───────────────────────────────────────────────
const $ = (id) => document.getElementById(id);
function setText(id, val) { const el = $(id); if (el) el.textContent = val; }
function setClass(id, cls) { const el = $(id); if (el) el.className = cls; }

// ── Toast Notification Helper ─────────────────────────────────
function showToast(message, type = 'success') {
    let toast = document.getElementById('hiltron-toast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'hiltron-toast';
        toast.style.cssText = `
            position: fixed;
            top: 24px;
            left: 50%;
            transform: translateX(-50%) translateY(-20px);
            z-index: 99999;
            padding: 12px 22px;
            border-radius: 12px;
            font-size: 13px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 10px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.6);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            opacity: 0;
            pointer-events: none;
        `;
        document.body.appendChild(toast);
    }
    
    if (type === 'success') {
        toast.style.background = 'rgba(16, 185, 129, 0.95)';
        toast.style.color = '#FFFFFF';
        toast.style.border = '1px solid rgba(255, 255, 255, 0.3)';
        toast.innerHTML = `<i class="fas fa-check-circle" style="font-size:16px;"></i> <span>${message}</span>`;
    } else if (type === 'warning') {
        toast.style.background = 'rgba(245, 158, 11, 0.95)';
        toast.style.color = '#FFFFFF';
        toast.style.border = '1px solid rgba(255, 255, 255, 0.3)';
        toast.innerHTML = `<i class="fas fa-exclamation-triangle" style="font-size:16px;"></i> <span>${message}</span>`;
    } else {
        toast.style.background = 'rgba(239, 68, 68, 0.95)';
        toast.style.color = '#FFFFFF';
        toast.style.border = '1px solid rgba(255, 255, 255, 0.3)';
        toast.innerHTML = `<i class="fas fa-circle-xmark" style="font-size:16px;"></i> <span>${message}</span>`;
    }
    
    requestAnimationFrame(() => {
        toast.style.opacity = '1';
        toast.style.transform = 'translateX(-50%) translateY(0)';
    });
    
    clearTimeout(toast._timeout);
    toast._timeout = setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(-50%) translateY(-20px)';
    }, 4500);
}

// ── UI Setup ──────────────────────────────────────────────────
function setupUI() {
    // Populate city dropdown
    renderCityDropdown();

    // City dropdown button
    $('city-dropdown-btn').addEventListener('click', (e) => {
        e.stopPropagation();
        const dd = $('city-dropdown');
        const ch = $('dropdown-chevron');
        const isOpen = dd.classList.contains('open');
        dd.classList.toggle('open', !isOpen);
        if (ch) ch.style.transform = isOpen ? '' : 'rotate(180deg)';
    });

    // Close dropdown on outside click
    document.addEventListener('click', () => {
        $('city-dropdown')?.classList.remove('open');
        const ch = $('dropdown-chevron');
        if (ch) ch.style.transform = '';
    });

    // Accordion toggles
    document.querySelectorAll('.accordion-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const target = $(btn.dataset.target);
            const icon   = $('icon-' + btn.dataset.target);
            if (!target) return;
            target.classList.toggle('collapsed');
            if (icon) icon.classList.toggle('open');
        });
    });

    // Time Slider (±720 min = ±12 hours)
    $('time-slider').addEventListener('input', (e) => {
        appState.timeOffsetMinutes = parseInt(e.target.value);
        updateSliderDisplay();
        updateUI();
    });

    // Live Play / Pause Toggle
    $('btn-time-play')?.addEventListener('click', () => {
        simState.isRunning = !simState.isRunning;
        simState.lastTickMs = Date.now();
        const icon = $('icon-time-play');
        const text = $('text-time-play');
        if (simState.isRunning) {
            if (icon) { icon.className = 'fas fa-pause'; icon.style.color = '#10B981'; }
            if (text) text.textContent = 'Live Ticking';
        } else {
            if (icon) { icon.className = 'fas fa-play'; icon.style.color = '#F59E0B'; }
            if (text) text.textContent = 'Jeda';
        }
    });

    // Reset ke Waktu Sekarang (Offset 0 & 1x speed)
    $('btn-time-reset')?.addEventListener('click', () => {
        appState.timeOffsetMinutes = 0;
        $('time-slider').value = '0';
        updateSliderDisplay();
        simState.speedMultiplier = 1;
        simState.isRunning = true;
        simState.simulatedElapsedSeconds = 0;
        simState.lastTickMs = Date.now();
        const icon = $('icon-time-play');
        const text = $('text-time-play');
        if (icon) { icon.className = 'fas fa-pause'; icon.style.color = '#10B981'; }
        if (text) text.textContent = 'Live Ticking';
        document.querySelectorAll('.speed-btn').forEach(b => {
            const is1x = b.dataset.speed === '1';
            b.classList.toggle('active', is1x);
            b.style.color = is1x ? '#10B981' : 'var(--c-muted)';
            b.style.background = is1x ? 'rgba(16,185,129,0.2)' : 'rgba(255,255,255,0.05)';
        });
        syncData();
    });

    // Speed buttons (1x, 10x, 60x)
    document.querySelectorAll('.speed-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const speed = parseInt(btn.dataset.speed) || 1;
            simState.speedMultiplier = speed;
            simState.isRunning = true;
            simState.lastTickMs = Date.now();
            const icon = $('icon-time-play');
            const text = $('text-time-play');
            if (icon) { icon.className = 'fas fa-pause'; icon.style.color = '#10B981'; }
            if (text) text.textContent = 'Live Ticking';

            document.querySelectorAll('.speed-btn').forEach(b => {
                const isActive = b === btn;
                b.classList.toggle('active', isActive);
                b.style.color = isActive ? '#10B981' : 'var(--c-muted)';
                b.style.background = isActive ? 'rgba(16,185,129,0.2)' : 'rgba(255,255,255,0.05)';
            });
        });
    });

    // Date Picker
    $('date-picker').value = appState.date;
    $('date-picker').addEventListener('change', (e) => {
        appState.date = e.target.value;
        simState.simulatedElapsedSeconds = 0;
        simState.lastTickMs = Date.now();
        syncData();
        fetchMap();
    });

    // Date "Hari Ini" quick button
    $('btn-date-today')?.addEventListener('click', () => {
        const localNow = new Date();
        const todayStr = `${localNow.getFullYear()}-${String(localNow.getMonth() + 1).padStart(2, '0')}-${String(localNow.getDate()).padStart(2, '0')}`;
        appState.date = todayStr;
        $('date-picker').value = todayStr;
        appState.timeOffsetMinutes = 0;
        $('time-slider').value = '0';
        updateSliderDisplay();
        simState.speedMultiplier = 1;
        simState.isRunning = true;
        simState.simulatedElapsedSeconds = 0;
        simState.lastTickMs = Date.now();
        syncData();
        fetchMap();
    });

    // Search form — try backend first, fallback to Nominatim
    $('search-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const query = $('city-search-input').value.trim();
        if (!query) return;
        setApiState('syncing');
        setText('api-status-text', 'Mencari…');

        let location = await fetchGeocode(query);
        if (!location) {
            // Fallback: Nominatim
            location = await geocodeNominatim(query);
        }

        if (location) {
            CITIES.push(location);
            if (globe) globe.addMarker(location.lat, location.lon);
            renderCityDropdown();
            await selectCity(CITIES.length - 1);
            $('city-search-input').value = '';
        } else {
            setApiState('error');
            setText('api-status-text', 'Lokasi tidak ditemukan');
            setTimeout(() => setApiState('ok'), 3000);
        }
    });

    // GPS / Current Location
    let myLocationIdx = null;

    async function detectAndApplyDeviceGPS() {
        if (!navigator.geolocation) {
            alert('Browser Anda tidak mendukung deteksi lokasi (GPS).');
            return;
        }

        const iconGps = $('btn-gps')?.querySelector('i');
        const btnDetectDevice = $('btn-detect-device-gps');

        if (iconGps) iconGps.className = 'fas fa-spinner fa-spin';
        if (btnDetectDevice) {
            btnDetectDevice.innerHTML = `<i class="fas fa-spinner fa-spin" style="margin-right:6px;"></i> Mendeteksi Lokasi GPS...`;
            btnDetectDevice.style.background = "#F59E0B";
        }

        setApiState('syncing');
        setText('api-status-text', 'Mencari Lokasi GPS…');

        navigator.geolocation.getCurrentPosition(
            async (pos) => {
                try {
                    const lat = pos.coords.latitude;
                    const lon = pos.coords.longitude;
                    const accuracy = Math.round(pos.coords.accuracy);

                    // Update Tampilan Kartu GPS Hardware/Device Panel
                    setText('gps-lat', `${lat.toFixed(5)}°`);
                    setText('gps-lon', `${lon.toFixed(5)}°`);
                    setText('gps-sats', `Akurasi ±${accuracy}m`);

                    const badge = $('gps-lock-badge');
                    if (badge) {
                        badge.textContent = "TERKUNCI (LOCKED)";
                        badge.style.background = "rgba(16,185,129,0.2)";
                        badge.style.color = "#10B981";
                        badge.style.border = "1px solid rgba(16,185,129,0.3)";
                    }

                    let name = `Lokasi Perangkat (${lat.toFixed(4)}°, ${lon.toFixed(4)}°)`;
                    const rev = await reverseGeocodeNominatim(lat, lon);
                    if (rev) name = rev;

                    if (myLocationIdx !== null && CITIES[myLocationIdx]) {
                        CITIES[myLocationIdx].name = name;
                        CITIES[myLocationIdx].lat  = lat;
                        CITIES[myLocationIdx].lon  = lon;
                    } else {
                        CITIES.push({ name, lat, lon });
                        myLocationIdx = CITIES.length - 1;
                        if (globe) globe.addMarker(lat, lon);
                    }

                    renderCityDropdown();
                    await selectCity(myLocationIdx);

                    if (btnDetectDevice) {
                        btnDetectDevice.innerHTML = `<i class="fas fa-check" style="margin-right:6px;"></i> Lokasi Terkunci!`;
                        btnDetectDevice.style.background = "#10B981";
                        setTimeout(() => {
                            btnDetectDevice.innerHTML = `<i class="fas fa-crosshairs" style="margin-right:6px;"></i> Ambil Lokasi GPS HP / Laptop`;
                        }, 3000);
                    }
                } catch (err) {
                    console.error("Error during GPS selectCity:", err);
                    setApiState('error');
                    setText('api-status-text', 'Gagal memproses data lokasi');
                    setTimeout(() => setApiState('ok'), 3000);
                } finally {
                    if (iconGps) iconGps.className = 'fas fa-crosshairs';
                }
            },
            (err) => {
                console.warn("Geolocation error:", err);
                setApiState('error');
                setText('api-status-text', 'Akses GPS Gagal/Ditolak');
                setTimeout(() => setApiState('ok'), 3000);
                if (iconGps) iconGps.className = 'fas fa-crosshairs';
                if (btnDetectDevice) {
                    btnDetectDevice.innerHTML = `<i class="fas fa-crosshairs" style="margin-right:6px;"></i> Coba Lagi Ambil Lokasi`;
                    btnDetectDevice.style.background = "#10B981";
                }
                alert("Gagal mengakses GPS. Pastikan izin lokasi diberikan pada browser.");
            },
            { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
        );
    }

    $('btn-gps')?.addEventListener('click', () => {
        if (myLocationIdx !== null && CITIES[myLocationIdx]) {
            if (appState.activeCityIdx === myLocationIdx) {
                if (globe) globe.focusCity(myLocationIdx);
            } else {
                selectCity(myLocationIdx);
            }
            return;
        }
        detectAndApplyDeviceGPS();
    });

    // Reset skydome camera
    $('btn-skydome-reset')?.addEventListener('click', () => {
        if (skydome) skydome.resetCamera();
    });

    // Map click on Globe → add custom pin and fetch data
    window.onMapClick = (lat, lon) => {
        const name = `${Math.abs(lat).toFixed(2)}°${lat >= 0 ? 'N' : 'S'}, ${Math.abs(lon).toFixed(2)}°${lon >= 0 ? 'E' : 'W'}`;
        const loc  = { name, lat, lon };
        CITIES.push(loc);
        if (globe) globe.addMarker(lat, lon);
        renderCityDropdown();
        selectCity(CITIES.length - 1);
    };

    // Mobile UI Drawers Toggle
    const btnLeft = $('btn-toggle-left');
    const btnRight = $('btn-toggle-right');
    const panelLeft = $('left-panel');
    const panelRight = $('right-panel');
    const backdrop = $('mobile-backdrop');

    function closeDrawers() {
        if(panelLeft) panelLeft.classList.remove('open');
        if(panelRight) panelRight.classList.remove('open');
        if(backdrop) backdrop.classList.remove('open');
    }
    
    if (btnLeft) {
        btnLeft.addEventListener('click', () => {
            closeDrawers();
            panelLeft.classList.add('open');
            backdrop.classList.add('open');
        });
    }
    if (btnRight) {
        btnRight.addEventListener('click', () => {
            closeDrawers();
            panelRight.classList.add('open');
            backdrop.classList.add('open');
        });
    }
    if (backdrop) {
        backdrop.addEventListener('click', closeDrawers);
    }

    // Tracker Button Logic
    $('btn-point')?.addEventListener('click', async () => {
        const trackerStatus = $('tracker-status');
        if (!trackerStatus) return;

        // Gunakan posisi Bulan/Hilal aktif sesuai simulasi dinamis
        const offsetH   = (simState.simulatedElapsedSeconds / 3600) + (appState.timeOffsetMinutes / 60);
        const mAlt = appState.baseMoonAlt - offsetH * 14.5;
        let mAz  = (appState.baseMoonAz  + offsetH * 14.5) % 360;
        if (mAz < 0) mAz += 360;

        const targetData = {
            target_azimuth: parseFloat(mAz.toFixed(2)),
            target_altitude: parseFloat(mAlt.toFixed(2))
        };

        const altNote = targetData.target_altitude < 0 
            ? `\n(Hilal di bawah ufuk, teleskop diarahkan ke ufuk barat 0°)` 
            : '';

        trackerStatus.innerText = "Status: Mengirim instruksi ke Teleskop...";
        trackerStatus.style.color = "#3B82F6"; // Blue

        // 1. Coba kirim instan melalui EMQX Cloud MQTT (Web Vercel -> ESP32)
        if (isMqttConnected()) {
            const sent = sendMqttCommand({
                command: 'POINT_HILAL',
                target_azimuth: targetData.target_azimuth,
                target_altitude: targetData.target_altitude
            });
            if (sent) {
                trackerStatus.style.color = "#10B981";
                trackerStatus.innerText = `Status: Terkirim via EMQX Cloud MQTT!\nTarget: Azimuth ${targetData.target_azimuth}°, Altitude ${targetData.target_altitude}°${altNote}`;
                showToast(`Target Hilal Terkirim ke ESP32! (Az: ${targetData.target_azimuth}°, Alt: ${targetData.target_altitude}°)`, "success");
                return;
            }
        }

        // 2. Fallback via Local REST API jika MQTT belum terhubung
        try {
            // Kita gunakan API_BASE yang sama dengan ephemeris
            const { API_BASE } = await import('./api.js');
            const response = await fetch(`${API_BASE}/point-hilal`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(targetData)
            });

            const result = await response.json();
            
            if (response.ok) {
                if (result.status === 'warning') {
                    trackerStatus.style.color = "#F59E0B"; // Orange
                    trackerStatus.innerText = `Status: ESP32 Belum Terhubung!\nPeriksa koneksi Wi-Fi ESP32.`;
                } else {
                    trackerStatus.style.color = "#10B981"; // Green
                    trackerStatus.innerText = `Status: Berhasil Terkirim!\nTarget: Azimuth ${targetData.target_azimuth}°, Altitude ${targetData.target_altitude}°${altNote}`;
                }
            } else {
                trackerStatus.style.color = "#EF4444"; // Red
                trackerStatus.innerText = `Status: Gagal dari Server.\nError: ${JSON.stringify(result)}`;
            }
        } catch (error) {
            console.error("Error:", error);
            trackerStatus.style.color = "#EF4444";
            trackerStatus.innerText = "Status: Terjadi kesalahan jaringan.";
        }
    });

    // ── Set Home / Kalibrasi Titik Nol (0° Ufuk & Hadap Utara) ──
    $('btn-set-home')?.addEventListener('click', async () => {
        const trackerStatus = $('tracker-status');
        if (trackerStatus) {
            trackerStatus.innerText = "Status: Mengirim instruksi Kalibrasi Titik Nol ke ESP32...";
            trackerStatus.style.color = "#3B82F6";
        }

        // 1. Coba kirim via EMQX Cloud MQTT
        if (isMqttConnected()) {
            const sent = sendMqttCommand({ command: 'SET_HOME' });
            if (sent) {
                if (trackerStatus) {
                    trackerStatus.style.color = "#10B981";
                    trackerStatus.innerText = "Status: Titik Nol Berhasil Ditetapkan via Cloud MQTT!\n(Posisi saat ini = 0° Hadap Utara & 0° Ufuk Datar)";
                }
                showToast("Titik Nol (Home) Berhasil Ditetapkan!", "success");
                return;
            }
        }

        // 2. Fallback via Local HTTP
        try {
            const { API_BASE } = await import('./api.js');
            const res = await fetch(`${API_BASE}/set-home`, { method: 'POST' });
            const resData = await res.json();
            if (trackerStatus) {
                if (resData.status === 'success') {
                    trackerStatus.style.color = "#10B981";
                    trackerStatus.innerText = "Status: Titik Nol Berhasil Ditetapkan!\n(Posisi saat ini = 0° Hadap Utara & 0° Ufuk Datar)";
                } else {
                    trackerStatus.style.color = "#F59E0B";
                    trackerStatus.innerText = `Status: ${resData.message || 'ESP32 belum terhubung'}`;
                }
            }
        } catch (err) {
            if (trackerStatus) {
                trackerStatus.style.color = "#EF4444";
                trackerStatus.innerText = "Status: Gagal menghubungi server backend.";
            }
        }
    });

    // ── Save Calibration to EEPROM / NVS ──
    const btnSaveCalib = $('btn-save-calib');
    btnSaveCalib?.addEventListener('click', async () => {
        const calMsg = $('cal-status-msg');
        const calBadge = $('cal-locked-badge');
        const originalHtml = btnSaveCalib.innerHTML;
        
        btnSaveCalib.disabled = true;
        btnSaveCalib.innerHTML = `<i class="fas fa-spinner fa-spin"></i> Merekam ke EEPROM...`;
        btnSaveCalib.style.background = 'rgba(59, 130, 246, 0.25)';
        btnSaveCalib.style.color = '#60A5FA';
        btnSaveCalib.style.border = '1px solid rgba(59, 130, 246, 0.4)';
        
        if (calMsg) {
            calMsg.style.display = 'block';
            calMsg.style.background = 'rgba(59, 130, 246, 0.15)';
            calMsg.style.color = '#93C5FD';
            calMsg.style.border = '1px solid rgba(59, 130, 246, 0.3)';
            calMsg.innerHTML = `<i class="fas fa-satellite-dish fa-spin" style="margin-right:6px;"></i> Mengirim instruksi rekam ke Flash NVS ESP32...`;
        }

        // 1. Coba kirim via EMQX Cloud MQTT
        if (isMqttConnected()) {
            const sent = sendMqttCommand({ command: 'SAVE_CALIBRATION' });
            if (sent) {
                btnSaveCalib.innerHTML = `<i class="fas fa-check-circle"></i> Berhasil Direkam & Dikunci!`;
                btnSaveCalib.style.background = '#059669';
                btnSaveCalib.style.color = '#FFFFFF';
                btnSaveCalib.style.border = '1px solid #10B981';
                
                if (calBadge) {
                    calBadge.innerHTML = '<i class="fas fa-shield-alt"></i> EEPROM TERKUNCI';
                    calBadge.style.background = 'rgba(16,185,129,0.2)';
                    calBadge.style.color = '#10B981';
                    calBadge.style.border = '1px solid rgba(16,185,129,0.4)';
                }

                if (calMsg) {
                    calMsg.style.display = 'block';
                    calMsg.style.background = 'rgba(16, 185, 129, 0.2)';
                    calMsg.style.color = '#10B981';
                    calMsg.style.border = '1px solid rgba(16, 185, 129, 0.4)';
                    calMsg.innerHTML = `<i class="fas fa-check-circle" style="margin-right:6px;"></i> <strong>SUKSES:</strong> Kalibrasi 3/3/3/3 berhasil disimpan permanen ke Flash NVS ESP32 via Cloud MQTT!`;
                }

                showToast("Kalibrasi Berhasil Direkam ke EEPROM via Cloud MQTT! (Terkunci)", "success");
                setTimeout(() => {
                    btnSaveCalib.disabled = false;
                    btnSaveCalib.innerHTML = originalHtml;
                    btnSaveCalib.style.background = 'rgba(16,185,129,0.15)';
                    btnSaveCalib.style.color = '#10B981';
                }, 6000);
                return;
            }
        }

        try {
            const { API_BASE } = await import('./api.js');
            const res = await fetch(`${API_BASE}/save-calibration`, { method: 'POST' });
            
            if (!res.ok) {
                if (res.status === 405 || res.status === 404) {
                    throw new Error("Server backend perlu di-restart agar rute baru aktif! (Tekan Ctrl+C di terminal lalu jalankan lagi)");
                }
                const errJson = await res.json().catch(() => ({}));
                throw new Error(errJson.detail || `Server error (${res.status})`);
            }

            const resData = await res.json();
            
            if (resData.status === 'success') {
                btnSaveCalib.innerHTML = `<i class="fas fa-check-circle"></i> Berhasil Direkam & Dikunci!`;
                btnSaveCalib.style.background = '#059669';
                btnSaveCalib.style.color = '#FFFFFF';
                btnSaveCalib.style.border = '1px solid #10B981';
                
                if (calBadge) {
                    calBadge.innerHTML = '<i class="fas fa-shield-alt"></i> EEPROM TERKUNCI';
                    calBadge.style.background = 'rgba(16,185,129,0.2)';
                    calBadge.style.color = '#10B981';
                    calBadge.style.border = '1px solid rgba(16,185,129,0.4)';
                }

                if (calMsg) {
                    calMsg.style.display = 'block';
                    calMsg.style.background = 'rgba(16, 185, 129, 0.2)';
                    calMsg.style.color = '#10B981';
                    calMsg.style.border = '1px solid rgba(16, 185, 129, 0.4)';
                    calMsg.innerHTML = `<i class="fas fa-check-circle" style="margin-right:6px;"></i> <strong>SUKSES:</strong> Kalibrasi 3/3/3/3 berhasil disimpan permanen ke Flash NVS ESP32! Anda tidak perlu memutar alat lagi saat dinyalakan berikutnya.`;
                }

                showToast("Kalibrasi Berhasil Direkam ke EEPROM ESP32! (Terkunci)", "success");
            } else {
                btnSaveCalib.innerHTML = `<i class="fas fa-exclamation-triangle"></i> Gagal Menyimpan`;
                btnSaveCalib.style.background = 'rgba(245, 158, 11, 0.2)';
                btnSaveCalib.style.color = '#F59E0B';
                
                if (calMsg) {
                    calMsg.style.display = 'block';
                    calMsg.style.background = 'rgba(245, 158, 11, 0.15)';
                    calMsg.style.color = '#F59E0B';
                    calMsg.style.border = '1px solid rgba(245, 158, 11, 0.3)';
                    calMsg.innerHTML = `<i class="fas fa-exclamation-triangle" style="margin-right:6px;"></i> ${resData.message || 'ESP32 belum terhubung ke Server.'}`;
                }

                showToast(resData.message || "ESP32 belum terhubung!", "warning");
            }
        } catch (err) {
            btnSaveCalib.innerHTML = `<i class="fas fa-circle-xmark"></i> ${err.message && err.message.includes('restart') ? 'Restart Server' : 'Gagal Menyimpan'}`;
            btnSaveCalib.style.background = 'rgba(239, 68, 68, 0.2)';
            btnSaveCalib.style.color = '#EF4444';
            
            if (calMsg) {
                calMsg.style.display = 'block';
                calMsg.style.background = 'rgba(239, 68, 68, 0.15)';
                calMsg.style.color = '#EF4444';
                calMsg.style.border = '1px solid rgba(239, 68, 68, 0.3)';
                calMsg.innerHTML = `<i class="fas fa-times-circle" style="margin-right:6px;"></i> ${err.message || 'Gagal menghubungi backend API.'}`;
            }

            showToast(err.message || "Gagal menghubungi server backend.", "error");
        } finally {
            setTimeout(() => {
                btnSaveCalib.disabled = false;
                btnSaveCalib.innerHTML = originalHtml;
                btnSaveCalib.style.background = 'rgba(16,185,129,0.15)';
                btnSaveCalib.style.color = '#10B981';
                btnSaveCalib.style.border = '1px solid rgba(16,185,129,0.3)';
            }, 6000);
        }
    });

    // ── Reset Calibration in EEPROM / NVS ──
    const btnClearCalib = $('btn-clear-calib');
    btnClearCalib?.addEventListener('click', async () => {
        if (!confirm("Apakah Anda yakin ingin mereset data kalibrasi BNO055 di EEPROM Flash ESP32?")) return;
        
        const calMsg = $('cal-status-msg');
        const calBadge = $('cal-locked-badge');

        // 1. Coba kirim via EMQX Cloud MQTT
        if (isMqttConnected()) {
            const sent = sendMqttCommand({ command: 'CLEAR_CALIBRATION' });
            if (sent) {
                if (calBadge) {
                    calBadge.innerHTML = '<i class="fas fa-unlock"></i> BELUM TERSIMPAN';
                    calBadge.style.background = 'rgba(239,68,68,0.15)';
                    calBadge.style.color = '#EF4444';
                    calBadge.style.border = '1px solid rgba(239,68,68,0.3)';
                }
                if (calMsg) {
                    calMsg.style.display = 'block';
                    calMsg.style.background = 'rgba(245, 158, 11, 0.15)';
                    calMsg.style.color = '#F59E0B';
                    calMsg.style.border = '1px solid rgba(245, 158, 11, 0.3)';
                    calMsg.innerHTML = `<i class="fas fa-rotate-left" style="margin-right:6px;"></i> Profil kalibrasi di EEPROM NVS berhasil dihapus via Cloud MQTT.`;
                }
                showToast("Profil EEPROM berhasil di-reset via Cloud MQTT.", "warning");
                return;
            }
        }
        
        try {
            const { API_BASE } = await import('./api.js');
            const res = await fetch(`${API_BASE}/clear-calibration`, { method: 'POST' });
            const resData = await res.json();
            
            if (resData.status === 'success') {
                if (calBadge) {
                    calBadge.innerHTML = '<i class="fas fa-unlock"></i> BELUM TERSIMPAN';
                    calBadge.style.background = 'rgba(239,68,68,0.15)';
                    calBadge.style.color = '#EF4444';
                    calBadge.style.border = '1px solid rgba(239,68,68,0.3)';
                }
                if (calMsg) {
                    calMsg.style.display = 'block';
                    calMsg.style.background = 'rgba(245, 158, 11, 0.15)';
                    calMsg.style.color = '#F59E0B';
                    calMsg.style.border = '1px solid rgba(245, 158, 11, 0.3)';
                    calMsg.innerHTML = `<i class="fas fa-rotate-left" style="margin-right:6px;"></i> Profil kalibrasi di EEPROM NVS berhasil dihapus.`;
                }
                showToast("Profil EEPROM berhasil di-reset.", "warning");
            } else {
                showToast(resData.message || "Gagal mereset kalibrasi", "error");
            }
        } catch (err) {
            showToast("Gagal menghubungi server backend.", "error");
        }
    });

    // ── Device GPS Detection (Laptop / Smartphone Browser Geolocation) ──
    $('btn-detect-device-gps')?.addEventListener('click', () => {
        detectAndApplyDeviceGPS();
    });

    // Apply Hardware GPS Coordinates (dari Modul NEO-6M ESP32 jika tersedia)
    $('btn-apply-gps')?.addEventListener('click', async () => {
        if (!latestGpsData) return;
        
        const gpsCityName = `Lokasi Modul GPS (${latestGpsData.lat.toFixed(4)}°, ${latestGpsData.lon.toFixed(4)}°)`;
        
        let existingIdx = CITIES.findIndex(c => c.isGps);
        if (existingIdx !== -1) {
            CITIES[existingIdx].name = gpsCityName;
            CITIES[existingIdx].lat  = latestGpsData.lat;
            CITIES[existingIdx].lon  = latestGpsData.lon;
            await selectCity(existingIdx);
        } else {
            CITIES.unshift({
                name: gpsCityName,
                lat: latestGpsData.lat,
                lon: latestGpsData.lon,
                isGps: true
            });
            await selectCity(0);
        }

        const btnGps = $('btn-apply-gps');
        if (btnGps) {
            const originalText = btnGps.innerHTML;
            btnGps.innerHTML = `<i class="fas fa-check" style="margin-right:6px;"></i> Koordinat Modul Diterapkan!`;
            setTimeout(() => {
                btnGps.innerHTML = originalText;
            }, 2500);
        }
    });
}

// ── Nominatim Geocoder Fallback ───────────────────────────────
async function geocodeNominatim(query) {
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 8000);
        const url = `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(query)}&format=json&limit=1`;
        const res = await fetch(url, { headers: { 'Accept-Language': 'id,en' }, signal: controller.signal });
        clearTimeout(timeoutId);
        if (!res.ok) return null;
        const data = await res.json();
        if (!data.length) return null;
        return {
            name: data[0].display_name.split(',').slice(0, 2).join(',').trim(),
            lat:  parseFloat(data[0].lat),
            lon:  parseFloat(data[0].lon),
        };
    } catch { return null; }
}

async function reverseGeocodeNominatim(lat, lon) {
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 8000);
        const url = `https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lon}&format=json`;
        const res = await fetch(url, { headers: { 'Accept-Language': 'id,en' }, signal: controller.signal });
        clearTimeout(timeoutId);
        if (!res.ok) return null;
        const data = await res.json();
        if (data && data.address) {
            const city = data.address.city || data.address.town || data.address.village || data.address.county;
            const state = data.address.state || data.address.country;
            if (city && state) return `${city}, ${state}`;
            return data.display_name.split(',').slice(0, 2).join(',').trim();
        }
        return null;
    } catch { return null; }
}

// ── City Dropdown Renderer ────────────────────────────────────
function renderCityDropdown() {
    const dd = $('city-dropdown');
    if (!dd) return;
    dd.innerHTML = '';
    CITIES.forEach((city, idx) => {
        const btn = document.createElement('div');
        btn.className = `city-option${idx === appState.activeCityIdx ? ' active' : ''}`;
        btn.innerHTML = `<i class="fas fa-map-marker-alt" style="font-size:10px;color:${idx === appState.activeCityIdx ? '#10B981' : 'rgba(226,232,240,0.4)'}"></i><span>${city.name}</span>`;
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            selectCity(idx);
            dd.classList.remove('open');
        });
        dd.appendChild(btn);
    });
}

// ── Select a City ─────────────────────────────────────────────
async function selectCity(idx) {
    appState.activeCityIdx = idx;
    const city = CITIES[idx];
    appState.lat = city.lat;
    appState.lon = city.lon;

    setText('active-city-label', city.name);
    setText('header-coords', `${Math.abs(city.lat).toFixed(4)}°${city.lat >= 0 ? 'N' : 'S'} ${Math.abs(city.lon).toFixed(4)}°${city.lon >= 0 ? 'E' : 'W'}`);
    setText('val-lat', `${city.lat.toFixed(6)}°`);
    setText('val-lon', `${city.lon.toFixed(6)}°`);

    // Reset time slider
    $('time-slider').value = '0';
    appState.timeOffsetMinutes = 0;
    updateSliderDisplay();

    // Focus globe camera
    if (globe) {
        globe.focusCity(idx);
    }

    renderCityDropdown();
    await syncData();
}

// ── Sync Data from Backend ────────────────────────────────────
async function syncData(options = { quiet: false }) {
    const city = CITIES[appState.activeCityIdx];
    if (!options.quiet) {
        setApiState('syncing');
        setText('api-status-text', 'Sinkronisasi…');
    }

    // Tentukan waktu target (live real-time atau kombinasi jam hari ini untuk tanggal terpilih)
    const localNow = new Date();
    const todayLocal = `${localNow.getFullYear()}-${String(localNow.getMonth() + 1).padStart(2, '0')}-${String(localNow.getDate()).padStart(2, '0')}`;
    const todayUtc = localNow.toISOString().split('T')[0];

    let ts;
    if (appState.date === todayUtc || appState.date === todayLocal) {
        // Mode waktu nyata: gunakan jam saat ini persis (+ offset slider jika ada)
        const targetDate = new Date(Date.now() + (appState.timeOffsetMinutes * 60000));
        ts = targetDate.toISOString();
    } else {
        // Tanggal lain: terapkan jam, menit, detik saat ini pada tanggal tersebut (+ offset slider)
        const h = String(localNow.getUTCHours()).padStart(2, '0');
        const m = String(localNow.getUTCMinutes()).padStart(2, '0');
        const s = String(localNow.getUTCSeconds()).padStart(2, '0');
        const baseIso = `${appState.date}T${h}:${m}:${s}Z`;
        const targetDate = new Date(new Date(baseIso).getTime() + (appState.timeOffsetMinutes * 60000));
        ts = targetDate.toISOString();
    }

    const data = await fetchEphemeris(city.lat, city.lon, appState.date, ts);

    if (data) {
        appState.baseTime      = new Date(data.time_utc);
        appState.sunsetTime    = new Date(data.sunset_utc);
        appState.baseSunAlt    = data.sun_alt  ?? 0;
        appState.baseSunAz     = data.sun_az   ?? 270;
        appState.baseSunRa     = data.sun_ra   ?? 0;
        appState.baseSunDec    = data.sun_dec  ?? 0;
        appState.baseMoonAlt   = data.moon_alt ?? 5;
        appState.baseMoonAz    = data.moon_az  ?? 285;
        appState.baseMoonRa    = data.moon_ra  ?? 0;
        appState.baseMoonDec   = data.moon_dec ?? 0;
        appState.baseArcl      = data.arcl     ?? 0;
        appState.baseArcv      = data.arcv     ?? 0;
        appState.baseGMST      = data.gmst_hours ?? 0;
        appState.status        = data.mabims_status ?? 'Tidak Diketahui';
        appState.illumination  = data.illumination  ?? 0;

        // Reset akumulasi detik simulasi karena koordinat sudah di-reanchor ke NASA JPL terbaru
        simState.simulatedElapsedSeconds = 0;
        simState.lastTickMs = Date.now();
        simState.lastAutoSyncTime = Date.now();

        // Update Hijri/date display
        if (data.hijri) {
            setText('ui-active-date', `${data.hijri.formatted}  /  ${appState.date}`);
        }

        updateUI();

        if (!options.quiet) {
            setApiState('ok');
            setText('api-status-text', 'API Sinkron');
        }
    } else {
        if (!options.quiet) {
            setApiState('error');
            setText('api-status-text', 'API Error');
        }
    }
}

// ── Fetch MABIMS Map ──────────────────────────────────────────
async function fetchMap() {
    const data = await fetchMabimsMap(appState.date);
    if (data && globe) globe.drawMabimsMap(data);
}

// ── Dynamic Real-Time Simulation Engine ───────────────────────
function tickSimulation() {
    const now = Date.now();
    const deltaRealSec = (now - simState.lastTickMs) / 1000;
    simState.lastTickMs = now;

    if (simState.isRunning && deltaRealSec > 0 && deltaRealSec < 5) {
        simState.simulatedElapsedSeconds += deltaRealSec * simState.speedMultiplier;

        // Background JPL ephemeris re-sync setiap 60 detik saat berjalan di 1x real-time
        if (simState.speedMultiplier === 1 && (now - simState.lastAutoSyncTime > 60000)) {
            simState.lastAutoSyncTime = now;
            syncData({ quiet: true });
        }
    }

    updateUI();
}

// ── Update All UI Elements ────────────────────────────────────
function updateUI() {
    // Total offset efektif dalam jam dari baseTime: detik dinamis berjalan + offset slider manual
    const elapsedH = simState.simulatedElapsedSeconds / 3600;
    const sliderH = appState.timeOffsetMinutes / 60;
    const totalOffsetH = elapsedH + sliderH;

    const activeTime = new Date(appState.baseTime.getTime() + (simState.simulatedElapsedSeconds * 1000) + (appState.timeOffsetMinutes * 60000));

    // Time displays (Local WIB/sistem dan UTC)
    const pad = (n) => String(n).padStart(2, '0');
    const locH = pad(activeTime.getHours());
    const locM = pad(activeTime.getMinutes());
    const locS = pad(activeTime.getSeconds());
    const utcH = pad(activeTime.getUTCHours());
    const utcM = pad(activeTime.getUTCMinutes());
    const utcS = pad(activeTime.getUTCSeconds());

    // Deteksi singkatan zona waktu lokal (misal: WIB, WITA, WIT)
    let tzAbbr = 'WIB';
    try {
        const parts = new Intl.DateTimeFormat('id-ID', { timeZoneName: 'short' }).formatToParts(activeTime);
        const match = parts.find(p => p.type === 'timeZoneName');
        if (match && match.value) tzAbbr = match.value;
    } catch (_) {}

    setText('val-time', `${locH}:${locM}:${locS} ${tzAbbr}`);
    setText('val-time-utc', `${utcH}:${utcM}:${utcS} UTC`);

    if (appState.sunsetTime) {
        const sH = pad(appState.sunsetTime.getHours());
        const sM = pad(appState.sunsetTime.getMinutes());
        setText('val-sunset', `${sH}:${sM} ${tzAbbr}`);
    }

    // Interpolated values for celestial bodies
    const sAlt = appState.baseSunAlt  - totalOffsetH * 15;
    let   sAz  = (appState.baseSunAz   + totalOffsetH * 15) % 360;
    if (sAz < 0) sAz += 360;

    const mAlt = appState.baseMoonAlt - totalOffsetH * 14.5;
    let   mAz  = (appState.baseMoonAz  + totalOffsetH * 14.5) % 360;
    if (mAz < 0) mAz += 360;

    // GMST: 1 mean solar hour = 1.00273790935 mean sidereal hours
    let activeGMST = (appState.baseGMST + totalOffsetH * 1.00273790935) % 24;
    if (activeGMST < 0) activeGMST += 24;

    setText('val-azisun',   `${sAz.toFixed(2)}°`);
    setText('val-altisun',  `${sAlt.toFixed(2)}°`);
    setText('val-azisab',   `${mAz.toFixed(2)}°`);
    setText('val-altimoon', `${mAlt.toFixed(2)}°`);
    setText('val-fraksi',   `${(appState.illumination * 100).toFixed(2)}%`);
    setText('ui-tinggi',    `${appState.baseArcv.toFixed(2)}°`);
    setText('ui-elongasi',  `${appState.baseArcl.toFixed(2)}°`);
    setText('val-gmst',     `${activeGMST.toFixed(4)} j`);

    // MABIMS Criteria check display
    const arcvOk = appState.baseArcv >= 3;
    const arclOk = appState.baseArcl >= 6.4;
    const critArcv = $('criteria-arcv');
    const critArcl = $('criteria-arcl');
    if (critArcv) {
        critArcv.textContent = `${appState.baseArcv.toFixed(2)}° ${arcvOk ? '✓' : '✗'}`;
        critArcv.className   = `hud-value ${arcvOk ? 'neon' : 'red'}`;
    }
    if (critArcl) {
        critArcl.textContent = `${appState.baseArcl.toFixed(2)}° ${arclOk ? '✓' : '✗'}`;
        critArcl.className   = `hud-value ${arclOk ? 'neon' : 'red'}`;
    }

    // Update globe dengan rotasi dinamis bumi sesuai GMST aktif
    if (globe) {
        globe.setEphemeris(activeGMST, appState.baseSunRa, appState.baseSunDec, appState.baseMoonRa, appState.baseMoonDec);
    }

    // Update skydome simulation
    if (skydome) {
        skydome.updateSimulation({
            ...appState,
            effectiveOffsetHours: totalOffsetH,
        });
    }

    // Status Card
    const statusCard = $('status-card');
    if (statusCard) {
        const s = appState.status;
        if (s === 'Imkanur Rukyat (MABIMS)') {
            statusCard.className = 'status-badge mabims';
            statusCard.innerHTML = '<i class="fas fa-check-circle"></i> Imkanur Rukyat (MABIMS)';
        } else if (s === 'Wujudul Hilal') {
            statusCard.className = 'status-badge wujudul';
            statusCard.innerHTML = '<i class="fas fa-moon"></i> Wujudul Hilal';
        } else {
            statusCard.className = 'status-badge belum';
            statusCard.innerHTML = '<i class="fas fa-times-circle"></i> Belum Wujud';
        }
    }
}

// ── Slider Display ────────────────────────────────────────────
function updateSliderDisplay() {
    const m = appState.timeOffsetMinutes;
    const sign = m > 0 ? '+' : '';
    const h = Math.floor(Math.abs(m) / 60);
    const min = Math.abs(m) % 60;
    const display = h > 0 ? `${sign}${m < 0 ? '-' : ''}${h}j ${min}m` : `${sign}${m} menit`;
    setText('slider-time-display', m === 0 ? '±0 menit' : display);
}

// ── API Status Pill ───────────────────────────────────────────
function setApiState(state) {
    const pill = $('api-pill');
    if (!pill) return;
    pill.className = `api-pill ${state === 'ok' ? '' : state}`;
    const dot = $('api-status-indicator');
    if (dot) {
        dot.style.background   = state === 'ok'      ? '#10B981'
                                : state === 'syncing' ? '#F59E0B'
                                : '#EF4444';
        dot.style.boxShadow    = `0 0 6px ${dot.style.background}`;
    }
    const txt = $('api-status-text');
    if (txt) {
        txt.style.color = state === 'ok'      ? '#10B981'
                        : state === 'syncing' ? '#F59E0B'
                        : '#EF4444';
    }
}

// ── Hardware Telemetry & GPS Updater ──────────────────────────
let latestGpsData = null;

export function renderTelemetryData(data) {
    if (!data) return;

    if (data.status === 'connected' || data.type === 'telemetry') {
        const azVal = (typeof data.azimuth === 'number') ? data.azimuth.toFixed(2) : (data.azimuth ?? '0.00');
        const altVal = (typeof data.altitude === 'number') ? data.altitude.toFixed(2) : (data.altitude ?? '0.00');
        setText('tel-azimuth', `${azVal}°`);
        setText('tel-altitude', `${altVal}°`);
        
        const isLocked = Boolean(data.cal_locked);
        const effectiveSys   = isLocked ? 3 : (data.cal_sys ?? 0);
        const effectiveGyro  = isLocked ? 3 : (data.cal_gyro ?? 0);
        const effectiveAccel = isLocked ? 3 : (data.cal_accel ?? 0);
        const effectiveMag   = isLocked ? 3 : (data.cal_mag ?? 0);

        const updateCal = (id, val) => {
            const el = $(id);
            if (el) {
                el.textContent = `${val}/3`;
                el.style.color = val === 3 ? '#10B981' : (val > 0 ? '#F59E0B' : '#EF4444');
            }
        };
        updateCal('cal-sys', effectiveSys);
        updateCal('cal-gyro', effectiveGyro);
        updateCal('cal-accel', effectiveAccel);
        updateCal('cal-mag', effectiveMag);

        // Update EEPROM Calibration Lock Badge
        const calBadge = $('cal-locked-badge');
        const calNotice = $('cal-locked-notice');
        if (calBadge) {
            if (isLocked) {
                calBadge.innerHTML = '<i class="fas fa-shield-alt"></i> EEPROM TERKUNCI';
                calBadge.style.background = 'rgba(16,185,129,0.2)';
                calBadge.style.color = '#10B981';
                calBadge.style.border = '1px solid rgba(16,185,129,0.4)';
                calBadge.title = 'Profil kalibrasi BNO055 tersimpan di Flash NVS aktif. Anda tidak perlu memutar alat lagi.';
                if (calNotice) calNotice.style.display = 'block';
            } else {
                calBadge.innerHTML = '<i class="fas fa-unlock"></i> BELUM TERSIMPAN';
                calBadge.style.background = 'rgba(239,68,68,0.15)';
                calBadge.style.color = '#EF4444';
                calBadge.style.border = '1px solid rgba(239,68,68,0.3)';
                calBadge.title = 'Belum ada profil kalibrasi di Flash NVS. Lakukan gerakan memadai lalu klik Simpan.';
                if (calNotice) calNotice.style.display = 'none';
            }
        }

        // Update Hardware GPS Telemetry
        const sats = $('gps-sats');
        const badge = $('gps-lock-badge');
        const btnGps = $('btn-apply-gps');

        if (data.gps_valid) {
            latestGpsData = { lat: data.gps_lat, lon: data.gps_lon };
            setText('gps-lat', `${data.gps_lat.toFixed(5)}°`);
            setText('gps-lon', `${data.gps_lon.toFixed(5)}°`);
            if (sats) sats.textContent = `${data.gps_sats || 0} Satelit (Modul)`;
            if (badge) {
                badge.textContent = "TERKUNCI (MODUL)";
                badge.style.background = "rgba(16,185,129,0.2)";
                badge.style.color = "#10B981";
                badge.style.border = "1px solid rgba(16,185,129,0.3)";
            }
            if (btnGps) {
                btnGps.style.display = "block";
                btnGps.disabled = false;
                btnGps.style.background = "#059669";
                btnGps.style.color = "#FFFFFF";
                btnGps.style.cursor = "pointer";
            }
        }
        
        const ts = $('tracker-status');
        if (ts && (ts.innerText.includes("Menunggu") || ts.innerText.includes("Terputus") || ts.innerText.includes("Offline"))) {
            ts.innerText = "Status: ESP32 Terhubung & Siap";
            ts.style.color = "#10B981";
        }
    } else {
        setText('tel-azimuth', `--`);
        setText('tel-altitude', `--`);
        const calBadge = $('cal-locked-badge');
        if (calBadge) {
            calBadge.innerHTML = '<i class="fas fa-power-off"></i> OFFLINE';
            calBadge.style.background = 'rgba(255,255,255,0.05)';
            calBadge.style.color = 'rgba(226,232,240,0.4)';
            calBadge.style.border = '1px solid var(--c-border)';
        }
        const ts = $('tracker-status');
        if (ts && !ts.innerText.includes("Mengirim")) {
            ts.innerText = "Status: ESP32 Terputus / Offline";
            ts.style.color = "#EF4444";
        }
    }
}

async function updateTelemetryUI() {
    // Lewati polling HTTP jika sudah terkoneksi langsung via Cloud MQTT
    if (isMqttConnected()) return;

    const data = await fetchTelemetry();
    if (!data) return;
    renderTelemetryData(data);
}

// ── Loading Screen Dismissal ──────────────────────────────────
function hideLoading() {
    const ls = $('loading-screen');
    if (ls) ls.classList.add('hidden');
}

// ── Bootstrap ─────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    setupUI();

    globe   = initGlobe(
        $('webgl-container'),
        CITIES,
        (idx) => selectCity(idx)
    );

    skydome = initSkydome(
        $('skydome-canvas-container'),
        $('skydome-labels-container')
    );

    // Initial data load
    await selectCity(0);
    fetchMap();

    // Show loading screen for at least 800ms for dramatic effect
    setTimeout(hideLoading, 900);

    // Start dynamic simulation loop (smooth 100ms updates)
    setInterval(tickSimulation, 100);

    // Inisialisasi MQTT Cloud Bridge untuk Vercel / Remote IoT
    initMqttBridge({
        onTelemetry: (data) => {
            renderTelemetryData(data);
        },
        onStatusChange: (isOnline) => {
            const ts = $('tracker-status');
            if (ts) {
                if (isOnline) {
                    if (ts.innerText.includes("Offline") || ts.innerText.includes("Menunggu") || ts.innerText.includes("Terputus")) {
                        ts.innerText = "Status: Terhubung ke Broker EMQX (Siap)";
                        ts.style.color = "#10B981";
                    }
                } else {
                    if (!ts.innerText.includes("Mengirim")) {
                        ts.innerText = "Status: Menunggu Sinyal ESP32...";
                        ts.style.color = "rgba(226,232,240,0.7)";
                    }
                }
            }
        }
    });

    // Start telemetry polling loop (sebagai cadangan saat running di localhost)
    setInterval(updateTelemetryUI, 1000);
});
