import { initGlobe }   from './globe.js';
import { initSkydome }  from './skydome.js';
import { fetchEphemeris, fetchMabimsMap, fetchGeocode } from './api.js';

/* ═══════════════════════════════════════════════════════════════
   FalakHub · main.js
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
        if (skydome) skydome.updateSimulation(appState);
    });

    // Date Picker
    $('date-picker').value = appState.date;
    $('date-picker').addEventListener('change', (e) => {
        appState.date = e.target.value;
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
    $('btn-gps')?.addEventListener('click', () => {
        if (myLocationIdx !== null && CITIES[myLocationIdx]) {
            // Already have location, just pan to it
            if (appState.activeCityIdx === myLocationIdx) {
                if (globe) globe.focusCity(myLocationIdx);
            } else {
                selectCity(myLocationIdx);
            }
            return;
        }

        if (!navigator.geolocation) {
            alert('Browser Anda tidak mendukung deteksi lokasi (GPS).');
            return;
        }

        setApiState('syncing');
        setText('api-status-text', 'Mencari Satelit GPS…');
        const icon = $('btn-gps').querySelector('i');
        if (icon) icon.className = 'fas fa-spinner fa-spin';

        navigator.geolocation.getCurrentPosition(
            async (pos) => {
                try {
                    const lat = pos.coords.latitude;
                    const lon = pos.coords.longitude;
                    let name = "Lokasi Saya";
                    
                    const rev = await reverseGeocodeNominatim(lat, lon);
                    if (rev) name = rev;

                    CITIES.push({ name, lat, lon });
                    if (globe) globe.addMarker(lat, lon);
                    myLocationIdx = CITIES.length - 1;
                    renderCityDropdown();
                    await selectCity(myLocationIdx);
                } catch (err) {
                    console.error("Error during GPS selectCity:", err);
                    setApiState('error');
                    setText('api-status-text', 'Gagal memproses data lokasi');
                    setTimeout(() => setApiState('ok'), 3000);
                } finally {
                    if (icon) icon.className = 'fas fa-crosshairs';
                }
            },
            (err) => {
                setApiState('error');
                setText('api-status-text', 'Akses GPS Gagal/Ditolak');
                setTimeout(() => setApiState('ok'), 3000);
                if (icon) icon.className = 'fas fa-crosshairs';
            },
            { enableHighAccuracy: true, timeout: 15000 }
        );
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
async function syncData() {
    const city = CITIES[appState.activeCityIdx];
    setApiState('syncing');
    setText('api-status-text', 'Sinkronisasi…');

    // If the selected date is today, use current time, else use noon UTC on that date
    const todayStr = new Date().toISOString().split('T')[0];
    let ts;
    if (appState.date === todayStr) {
        ts = new Date().toISOString();
    } else {
        ts = new Date(appState.date + "T12:00:00Z").toISOString();
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

        // Update Globe (absolute ephemeris)
        if (globe) {
            globe.setEphemeris(
                appState.baseGMST,
                appState.baseSunRa,  appState.baseSunDec,
                appState.baseMoonRa, appState.baseMoonDec
            );
        }

        // Update Hijri/date display
        if (data.hijri) {
            setText('ui-active-date', `${data.hijri.formatted}  /  ${appState.date}`);
        }

        updateUI();
        if (skydome) skydome.updateSimulation(appState);

        setApiState('ok');
        setText('api-status-text', 'API Sinkron');
    } else {
        setApiState('error');
        setText('api-status-text', 'API Error');
    }
}

// ── Fetch MABIMS Map ──────────────────────────────────────────
async function fetchMap() {
    const data = await fetchMabimsMap(appState.date);
    if (data && globe) globe.drawMabimsMap(data);
}

// ── Update All UI Elements ────────────────────────────────────
function updateUI() {
    const offsetH   = appState.timeOffsetMinutes / 60;
    const activeTime = new Date(appState.baseTime.getTime() + appState.timeOffsetMinutes * 60000);

    // Time displays
    setText('val-time', activeTime.toLocaleTimeString('id-ID', {
        hour: '2-digit', minute: '2-digit', second: '2-digit', timeZone: 'UTC'
    }) + ' UTC');
    if (appState.sunsetTime) {
        setText('val-sunset', appState.sunsetTime.toLocaleTimeString('id-ID', {
            hour: '2-digit', minute: '2-digit', timeZone: 'UTC'
        }) + ' UTC');
    }

    // Interpolated values for time slider
    const sAlt = appState.baseSunAlt  - offsetH * 15;
    const sAz  = appState.baseSunAz   + offsetH * 15;
    const mAlt = appState.baseMoonAlt - offsetH * 14.5;
    const mAz  = appState.baseMoonAz  + offsetH * 14.5;

    setText('val-azisun',   `${sAz.toFixed(2)}°`);
    setText('val-altisun',  `${sAlt.toFixed(2)}°`);
    setText('val-azisab',   `${mAz.toFixed(2)}°`);
    setText('val-altimoon', `${mAlt.toFixed(2)}°`);
    setText('val-fraksi',   `${(appState.illumination * 100).toFixed(2)}%`);
    setText('ui-tinggi',    `${appState.baseArcv.toFixed(2)}°`);
    setText('ui-elongasi',  `${appState.baseArcl.toFixed(2)}°`);
    setText('val-gmst',     `${appState.baseGMST.toFixed(4)} j`);

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

    // Update globe with interpolated positions on slider move
    if (globe) {
        const activeGMST = appState.baseGMST + offsetH;
        globe.setEphemeris(activeGMST, appState.baseSunRa, appState.baseSunDec, appState.baseMoonRa, appState.baseMoonDec);
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
});
