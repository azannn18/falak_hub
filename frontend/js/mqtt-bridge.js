/* ═══════════════════════════════════════════════════════════════
   HILTRON · mqtt-bridge.js
   Jembatan IoT Real-time untuk menghubungkan Frontend (Vercel)
   langsung ke mikrokontroler ESP32 menggunakan EMQX Public Broker.
   100% Gratis, Tanpa Kartu Kredit, Tanpa Perlu Daftar Akun.
═══════════════════════════════════════════════════════════════ */

export const MQTT_CONFIG = {
    // EMQX Public Broker WSS port 8084 (WebSocket Secure dengan SSL)
    brokerUrl: 'wss://broker.emqx.io:8084/mqtt',
    topics: {
        command:   'hiltron/tracker/command',
        telemetry: 'hiltron/tracker/telemetry',
        status:    'hiltron/tracker/status'
    }
};

let mqttClient = null;
let isConnected = false;
let onTelemetryCallback = null;
let onStatusChangeCallback = null;

export function initMqttBridge(callbacks = {}) {
    onTelemetryCallback = callbacks.onTelemetry || null;
    onStatusChangeCallback = callbacks.onStatusChange || null;

    if (typeof window.mqtt === 'undefined') {
        console.warn('[MQTT] Library mqtt.js belum dimuat dari CDN.');
        return;
    }

    const clientId = 'hiltron_web_' + Math.random().toString(16).substring(2, 10);
    console.log('[MQTT] Menghubungkan ke EMQX Public Broker:', MQTT_CONFIG.brokerUrl, '| ClientId:', clientId);

    try {
        mqttClient = window.mqtt.connect(MQTT_CONFIG.brokerUrl, {
            clientId: clientId,
            clean: true,
            connectTimeout: 10000,
            reconnectPeriod: 3000,
        });

        mqttClient.on('connect', () => {
            isConnected = true;
            console.log('[MQTT] ✅ Terhubung ke EMQX Public Broker!');
            if (onStatusChangeCallback) onStatusChangeCallback(true);

            // Berlangganan (Subscribe) ke telemetri dan status ESP32
            mqttClient.subscribe([MQTT_CONFIG.topics.telemetry, MQTT_CONFIG.topics.status], (err) => {
                if (err) {
                    console.error('[MQTT] Gagal subscribe ke topik:', err);
                } else {
                    console.log('[MQTT] Berhasil subscribe ke topik telemetri & status ESP32.');
                }
            });
        });

        mqttClient.on('message', (topic, payload) => {
            try {
                const messageStr = payload.toString();
                if (topic === MQTT_CONFIG.topics.telemetry) {
                    const data = JSON.parse(messageStr);
                    if (onTelemetryCallback) {
                        onTelemetryCallback(data);
                    }
                } else if (topic === MQTT_CONFIG.topics.status) {
                    const isOnline = (messageStr.trim() === 'online');
                    console.log(`[MQTT] Status Hardware ESP32: ${isOnline ? 'ONLINE' : 'OFFLINE'}`);
                    if (onStatusChangeCallback) onStatusChangeCallback(isOnline);
                }
            } catch (e) {
                console.error('[MQTT] Gagal parsing pesan telemetri:', e);
            }
        });

        mqttClient.on('error', (err) => {
            console.warn('[MQTT] Error:', err);
        });

        mqttClient.on('close', () => {
            if (isConnected) {
                isConnected = false;
                console.log('[MQTT] Terputus dari Broker EMQX.');
                if (onStatusChangeCallback) onStatusChangeCallback(false);
            }
        });
    } catch (e) {
        console.error('[MQTT] Gagal menginisialisasi MQTT client:', e);
    }
}

export function sendMqttCommand(commandPayload) {
    if (!mqttClient || !isConnected) {
        console.warn('[MQTT] Belum terhubung ke Broker EMQX.');
        return false;
    }
    const payloadStr = JSON.stringify(commandPayload);
    mqttClient.publish(MQTT_CONFIG.topics.command, payloadStr, { qos: 1 }, (err) => {
        if (err) {
            console.error('[MQTT] Gagal mengirim pesan ke topik:', err);
        } else {
            console.log('[MQTT] Perintah terkirim ke ESP32:', commandPayload.command);
        }
    });
    return true;
}

export function isMqttConnected() {
    return isConnected;
}

