/**
 * HILTRON — Falak Voice AI Assistant (ChatGPT Voice Style)
 * Persona: Hilmi (Santri Astronom Digital HILTRON Falak Hub)
 * Fluid Audio-Reactive Cosmic Orb + Real-Time Voice Conversation Loop
 */

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// ═══════════════════════════════════════════ STATE ═══
const state = {
    isListening: false,
    isSpeaking: false,
    isThinking: false,
    speechRecognition: null,
    speechSynthesis: window.speechSynthesis || null,
    selectedVoice: null,
    selectedNeuralVoice: 'id-ID-ArdiNeural',
    audioPlayer: null,
    audioContext: null,
    analyser: null,          // Mic analyser
    audioDataArray: null,    // Mic data array
    speakerAnalyser: null,   // TTS output analyser for Orb reaction
    speakerDataArray: null,  // TTS audio data array
    speakerGain: null,       // Master TTS gain node for smooth fade and barge-in
    micStream: null,
    clock: new THREE.Clock(),
    userLocation: { lat: -6.175392, lon: 106.827153 },
    chatHistory: [],
    activeAbortController: null // AbortController for active SSE streaming
};

// ═══════════════════════════════════════════ THREE.JS FLUID COSMIC ORB ═══
let scene, camera, renderer, controls, starField, particleRings;
let cosmicOrb, orbGeometry, originalPositions, orbLight, orbInnerLight;

function initThreeJS() {
    const container = document.getElementById('avatar-canvas-container');
    const canvas = document.getElementById('avatar-canvas');
    if (!container || !canvas) return;

    const width = container.clientWidth;
    const height = container.clientHeight;

    // 1. Scene
    scene = new THREE.Scene();

    // 2. Camera
    camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.set(0, 0, 3.8);

    // 3. Renderer
    renderer = new THREE.WebGLRenderer({ canvas: canvas, alpha: true, antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.2;

    // 4. Orbit Controls (gentle interaction)
    controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.enableZoom = false; // keep centered focus like ChatGPT
    controls.enablePan = false;
    controls.maxPolarAngle = Math.PI / 1.7;
    controls.minPolarAngle = Math.PI / 2.3;

    // 5. Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambientLight);

    orbLight = new THREE.PointLight(0x10B981, 3.5, 12);
    orbLight.position.set(0, 0, 0);
    scene.add(orbLight);

    const cyanRim = new THREE.DirectionalLight(0x06B6D4, 2.0);
    cyanRim.position.set(3, 3, 4);
    scene.add(cyanRim);

    const goldRim = new THREE.DirectionalLight(0xF59E0B, 1.2);
    goldRim.position.set(-3, -2, 3);
    scene.add(goldRim);

    // 6. Build Fluid Morphing Orb
    createCosmicOrb();

    // 7. Celestial Holographic Rings & Star Dust
    createStarField();
    createHolographicRings();

    // 8. Resize Handler
    window.addEventListener('resize', onWindowResize);

    // 9. Animation Loop
    animate();
}

function createCosmicOrb() {
    // Ultra-smooth sphere for liquid fluid distortion (ChatGPT Voice style)
    const radius = 1.25;
    orbGeometry = new THREE.SphereGeometry(radius, 96, 96);
    originalPositions = orbGeometry.attributes.position.clone();

    // Silky smooth, glowing iridescent PBR material
    const orbMaterial = new THREE.MeshPhysicalMaterial({
        color: 0x052e25,
        emissive: 0x10B981,
        emissiveIntensity: 0.55,
        roughness: 0.1,
        metalness: 0.15,
        clearcoat: 1.0,
        clearcoatRoughness: 0.1,
        transmission: 0.45,
        ior: 1.35,
        transparent: true,
        opacity: 0.95,
        wireframe: false
    });

    cosmicOrb = new THREE.Mesh(orbGeometry, orbMaterial);
    scene.add(cosmicOrb);

    // Inner Radiant Energy Core
    const innerGeo = new THREE.SphereGeometry(radius * 0.75, 48, 48);
    const innerMat = new THREE.MeshBasicMaterial({
        color: 0x06B6D4,
        transparent: true,
        opacity: 0.35,
        blending: THREE.AdditiveBlending
    });
    orbInnerLight = new THREE.Mesh(innerGeo, innerMat);
    cosmicOrb.add(orbInnerLight);
}

function createStarField() {
    const starCount = 650;
    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(starCount * 3);
    const colors = new Float32Array(starCount * 3);

    for (let i = 0; i < starCount * 3; i += 3) {
        positions[i] = (Math.random() - 0.5) * 16;
        positions[i + 1] = (Math.random() - 0.5) * 16;
        positions[i + 2] = (Math.random() - 0.5) * 16;

        const r = Math.random();
        if (r > 0.6) {
            colors[i] = 0.06; colors[i + 1] = 0.73; colors[i + 2] = 0.51; // Emerald
        } else if (r > 0.3) {
            colors[i] = 0.02; colors[i + 1] = 0.71; colors[i + 2] = 0.83; // Cyan
        } else {
            colors[i] = 0.96; colors[i + 1] = 0.98; colors[i + 2] = 1.0;
        }
    }

    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

    const material = new THREE.PointsMaterial({
        size: 0.035,
        vertexColors: true,
        transparent: true,
        opacity: 0.7
    });

    starField = new THREE.Points(geometry, material);
    scene.add(starField);
}

function createHolographicRings() {
    particleRings = new THREE.Group();

    // Astrolabe Ecliptic Rings
    const ring1Geo = new THREE.RingGeometry(1.65, 1.67, 64);
    const ring1Mat = new THREE.MeshBasicMaterial({ color: 0x06B6D4, side: THREE.DoubleSide, transparent: true, opacity: 0.35 });
    const ring1 = new THREE.Mesh(ring1Geo, ring1Mat);
    ring1.rotation.x = Math.PI / 2.3;
    particleRings.add(ring1);

    const ring2Geo = new THREE.RingGeometry(1.9, 1.915, 64);
    const ring2Mat = new THREE.MeshBasicMaterial({ color: 0x10B981, side: THREE.DoubleSide, transparent: true, opacity: 0.25 });
    const ring2 = new THREE.Mesh(ring2Geo, ring2Mat);
    ring2.rotation.x = Math.PI / 2.8;
    ring2.rotation.y = 0.4;
    particleRings.add(ring2);

    scene.add(particleRings);
}

function onWindowResize() {
    const container = document.getElementById('avatar-canvas-container');
    if (!container || !camera || !renderer) return;
    const width = container.clientWidth;
    const height = container.clientHeight;
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height);
}

// ═══════════════════════════════════════════ FLUID MORPHING ORB ANIMATION ═══
function animate() {
    requestAnimationFrame(animate);

    const delta = state.clock.getDelta();
    const time = state.clock.getElapsedTime();

    // Rotate Celestial Rings & Stars
    if (particleRings) particleRings.rotation.z += 0.002;
    if (starField) starField.rotation.y += 0.0004;

    // Fluid Orb Vertex Displacement
    if (cosmicOrb && orbGeometry) {
        cosmicOrb.rotation.y += 0.005;
        cosmicOrb.rotation.x += 0.003;

        // Calculate Audio Level if Mic or TTS Speaking is active
        let audioLevel = 0;
        if (state.analyser && state.audioDataArray && state.isListening) {
            state.analyser.getByteFrequencyData(state.audioDataArray);
            let sum = 0;
            for (let i = 0; i < state.audioDataArray.length; i++) {
                sum += state.audioDataArray[i];
            }
            audioLevel = sum / (state.audioDataArray.length * 255); // 0 to 1
        } else if (state.speakerAnalyser && state.speakerDataArray && state.isSpeaking) {
            state.speakerAnalyser.getByteFrequencyData(state.speakerDataArray);
            let sum = 0;
            for (let i = 0; i < state.speakerDataArray.length; i++) {
                sum += state.speakerDataArray[i];
            }
            audioLevel = sum / (state.speakerDataArray.length * 255); // 0 to 1
        }

        // Modulation parameters based on state
        let waveAmp = 0.08;
        let waveFreq = 2.2;
        let speed = 2.5;

        if (state.isListening) {
            waveAmp = 0.12 + (audioLevel * 0.22);
            waveFreq = 3.8;
            speed = 4.5;
            orbLight.color.setHex(0xEF4444);
            cosmicOrb.material.emissive.setHex(0x991b1b);
        } else if (state.isThinking) {
            waveAmp = 0.15;
            waveFreq = 5.0;
            speed = 6.0;
            orbLight.color.setHex(0xF59E0B);
            cosmicOrb.material.emissive.setHex(0xb45309);
        } else if (state.isSpeaking) {
            // Real voice acoustic waves displacement (lipsync / frequency sync)
            const speechPulse = audioLevel * 0.35;
            waveAmp = 0.10 + speechPulse;
            waveFreq = 3.2 + (audioLevel * 2.5);
            speed = 4.0 + (audioLevel * 4.0);
            orbLight.color.setHex(0x06B6D4);
            cosmicOrb.material.emissive.setHex(0x0e7490);
        } else {
            // Idle
            orbLight.color.setHex(0x10B981);
            cosmicOrb.material.emissive.setHex(0x064e3b);
        }

        if (orbInnerLight) {
            const coreScale = 1.0 + Math.sin(time * 2.5) * 0.05;
            orbInnerLight.scale.setScalar(coreScale);
        }

        // Displace sphere vertices along their normals
        const posAttr = orbGeometry.attributes.position;
        const origAttr = originalPositions;

        for (let i = 0; i < posAttr.count; i++) {
            const ox = origAttr.getX(i);
            const oy = origAttr.getY(i);
            const oz = origAttr.getZ(i);

            // Perlin-style harmonic sine distortion
            const noise = Math.sin(ox * waveFreq + time * speed) *
                          Math.cos(oy * waveFreq + time * speed * 0.8) *
                          Math.sin(oz * waveFreq + time * speed * 1.2);

            const displacement = 1.0 + (noise * waveAmp);

            posAttr.setXYZ(i, ox * displacement, oy * displacement, oz * displacement);
        }

        posAttr.needsUpdate = true;
        orbGeometry.computeVertexNormals();
    }

    controls.update();
    renderer.render(scene, camera);
}

// ═══════════════════════════════════════════ REAL-TIME AUDIO (MIC & SPEAKER ANALYSER) ═══
async function initAudioAnalyser() {
    if (!state.audioContext) {
        try {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            state.audioContext = new AudioContext();

            // Speaker Gain Node (untuk master volume & fast fade out saat barge-in)
            state.speakerGain = state.audioContext.createGain();
            state.speakerGain.gain.setValueAtTime(1.0, state.audioContext.currentTime);

            // Speaker Analyser Node (untuk reaksi gelombang suara Orb saat asisten berbicara)
            state.speakerAnalyser = state.audioContext.createAnalyser();
            state.speakerAnalyser.fftSize = 64;
            state.speakerDataArray = new Uint8Array(state.speakerAnalyser.frequencyBinCount);

            state.speakerAnalyser.connect(state.speakerGain);
            state.speakerGain.connect(state.audioContext.destination);
        } catch (e) {
            console.log('AudioContext init error:', e.message);
        }
    }

    if (state.audioContext && state.audioContext.state === 'suspended') {
        try { await state.audioContext.resume(); } catch (e) {}
    }

    if (!state.micStream && state.audioContext) {
        try {
            state.micStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            });
            const source = state.audioContext.createMediaStreamSource(state.micStream);
            state.analyser = state.audioContext.createAnalyser();
            state.analyser.fftSize = 64;
            state.audioDataArray = new Uint8Array(state.analyser.frequencyBinCount);
            source.connect(state.analyser);
        } catch (e) {
            console.log('Microphone access passthrough:', e.message);
        }
    }
}

// ═══════════════════════════════════════════ BARGE-IN & STT VOICE RECOGNITION ═══
let speechDebounceTimer = null;

function triggerBargeIn() {
    if (!state.isSpeaking && !state.isThinking) return;
    console.log('[BargeIn] Interupsi suara pengguna terdeteksi! Memotong ucapan HILMI.');

    // 1. Matikan pemutaran audio secara instan (fade 30ms tanpa bunyi klik)
    gaplessPlayer.reset(true);
    if (state.speechSynthesis && state.speechSynthesis.speaking) {
        state.speechSynthesis.cancel();
    }

    // 2. Batalkan stream SSE yang sedang berjalan di background
    if (state.activeAbortController) {
        state.activeAbortController.abort();
        state.activeAbortController = null;
    }

    state.isSpeaking = false;
    state.isThinking = false;
    updateUIState('listening');
    setSubtitle('Hilmi mendengarkan Anda...', 'user');
}

function initSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        console.warn('Web Speech Recognition API tidak didukung di browser ini.');
        return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = 'id-ID';
    recognition.continuous = true; // Continuous recognition agar bisa mendeteksi suara saat asisten bicara (Barge-in)
    recognition.interimResults = true;

    recognition.onstart = () => {
        state.isListening = true;
        updateUIState('listening');
        setSubtitle('Hilmi sedang mendengarkan Anda...', 'user');
    };

    recognition.onspeechstart = () => {
        if (state.isSpeaking || state.isThinking) {
            triggerBargeIn();
        }
    };

    recognition.onresult = (event) => {
        let interimTranscript = '';
        let finalTranscript = '';

        for (let i = event.resultIndex; i < event.results.length; ++i) {
            if (event.results[i].isFinal) {
                finalTranscript += event.results[i][0].transcript;
            } else {
                interimTranscript += event.results[i][0].transcript;
            }
        }

        const currentText = (finalTranscript || interimTranscript).trim();
        if (currentText) {
            // Jika ada suara saat asisten sedang bicara, langsung potong (barge-in)
            if (state.isSpeaking || state.isThinking) {
                triggerBargeIn();
            }
            setSubtitle(`"${currentText}"`, 'user');

            // Smart Debounce: Beri toleransi jeda 850ms agar kalimat pengguna tidak terpotong saat menarik nafas
            if (speechDebounceTimer) clearTimeout(speechDebounceTimer);
            speechDebounceTimer = setTimeout(() => {
                if (currentText.length >= 2) {
                    if (state.speechRecognition) {
                        try { state.speechRecognition.stop(); } catch (e) {}
                    }
                    handleUserQuery(currentText);
                }
            }, 850);
        }

        if (finalTranscript && finalTranscript.trim().length >= 2) {
            if (speechDebounceTimer) clearTimeout(speechDebounceTimer);
            if (state.speechRecognition) {
                try { state.speechRecognition.stop(); } catch (e) {}
            }
            handleUserQuery(finalTranscript.trim());
        }
    };

    recognition.onerror = (event) => {
        console.error('Speech recognition error:', event.error);
        state.isListening = false;
        if (!state.isSpeaking && !state.isThinking) {
            updateUIState('idle');
        }
        if (event.error === 'not-allowed') {
            setSubtitle('Izin mikrofon belum diberikan. Silakan aktifkan izin mikrofon di browser.', 'hilmi');
        }
    };

    recognition.onend = () => {
        state.isListening = false;
        if (!state.isThinking && !state.isSpeaking) {
            updateUIState('idle');
        }
    };

    state.speechRecognition = recognition;
}

async function toggleListening() {
    await initAudioAnalyser();

    if (!state.speechRecognition) {
        initSpeechRecognition();
    }

    if (state.isListening) {
        state.speechRecognition.stop();
        state.isListening = false;
        updateUIState('idle');
    } else {
        gaplessPlayer.reset(true);
        if (state.speechSynthesis && state.speechSynthesis.speaking) {
            state.speechSynthesis.cancel();
        }
        try {
            state.speechRecognition.start();
        } catch (e) {
            state.speechRecognition.stop();
            setTimeout(() => state.speechRecognition.start(), 200);
        }
    }
}

// ═══════════════════════════════════════════ SPEECH SYNTHESIS (TTS) ═══
function initSpeechSynthesis() {
    if (!state.speechSynthesis) return;

    function populateVoices() {
        const voices = state.speechSynthesis.getVoices();
        state.selectedVoice = voices.find(v => v.lang.startsWith('id') || v.lang.includes('ID')) || null;
    }

    populateVoices();
    if (speechSynthesis.onvoiceschanged !== undefined) {
        speechSynthesis.onvoiceschanged = populateVoices;
    }
}

// ═══════════════════════════════════════════ GAPLESS WEB AUDIO STREAMING PLAYER ═══
// Menjamin setiap potongan kalimat dari streaming LLM diputar mulus tanpa celah (gapless)
// menggunakan Web Audio API (AudioContext + AudioBufferSourceNode + 25ms crossfade + cache).
const gaplessPlayer = {
    queue: [],                   // Antrean { text, bufferPromise, utteranceId }
    activeSources: [],           // AudioBufferSourceNode yang sedang aktif
    audioBufferCache: new Map(), // In-memory cache (voice::text -> AudioBuffer)
    nextScheduledTime: 0,
    isPlaying: false,
    isStreamFinished: false,
    currentUtteranceId: 0,

    ensureAudioContext() {
        if (!state.audioContext) {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            state.audioContext = new AudioContext();
        }
        if (!state.speakerGain) {
            state.speakerGain = state.audioContext.createGain();
            state.speakerGain.gain.setValueAtTime(1.0, state.audioContext.currentTime);

            state.speakerAnalyser = state.audioContext.createAnalyser();
            state.speakerAnalyser.fftSize = 64;
            state.speakerDataArray = new Uint8Array(state.speakerAnalyser.frequencyBinCount);

            state.speakerAnalyser.connect(state.speakerGain);
            state.speakerGain.connect(state.audioContext.destination);
        }
        if (state.audioContext.state === 'suspended') {
            state.audioContext.resume().catch(() => {});
        }
    },

    reset(immediate = true) {
        this.currentUtteranceId++;
        this.queue = [];
        this.isStreamFinished = false;

        if (state.audioContext && state.speakerGain) {
            if (immediate) {
                try {
                    const now = state.audioContext.currentTime;
                    state.speakerGain.gain.cancelScheduledValues(now);
                    state.speakerGain.gain.linearRampToValueAtTime(0.001, now + 0.03);
                } catch (e) {}
            }
        }

        // Hentikan seluruh source node aktif
        for (const src of this.activeSources) {
            try {
                src.stop(state.audioContext ? state.audioContext.currentTime + 0.03 : 0);
                src.disconnect();
            } catch (e) {}
        }
        this.activeSources = [];

        setTimeout(() => {
            if (state.audioContext && state.speakerGain) {
                try {
                    state.speakerGain.gain.cancelScheduledValues(state.audioContext.currentTime);
                    state.speakerGain.gain.setValueAtTime(1.0, state.audioContext.currentTime);
                } catch (e) {}
            }
        }, 50);

        if (state.speechSynthesis && state.speechSynthesis.speaking) {
            state.speechSynthesis.cancel();
        }

        this.isPlaying = false;
        this.nextScheduledTime = 0;
        state.isSpeaking = false;
        if (!state.isThinking && !state.isListening) {
            updateUIState('idle');
        }
    },

    async fetchAndDecodeAudio(text, voice) {
        const cacheKey = `${voice}::${text.trim()}`;
        if (this.audioBufferCache.has(cacheKey)) {
            return this.audioBufferCache.get(cacheKey);
        }

        try {
            const res = await fetch('/api/assistant/tts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    text: text,
                    voice: voice,
                    rate: '+0%',
                    pitch: '+0Hz'
                })
            });

            if (!res.ok) throw new Error(`TTS status ${res.status}`);
            const arrayBuffer = await res.arrayBuffer();
            this.ensureAudioContext();

            const audioBuffer = await state.audioContext.decodeAudioData(arrayBuffer);
            this.audioBufferCache.set(cacheKey, audioBuffer);
            return audioBuffer;
        } catch (err) {
            console.warn('[GaplessPlayer] Gagal fetch/decode audio:', err);
            return null;
        }
    },

    enqueue(text) {
        if (!text || !text.trim()) return;
        this.ensureAudioContext();

        const voiceChoice = state.selectedNeuralVoice || 'id-ID-ArdiNeural';
        const utteranceId = this.currentUtteranceId;

        // Mulai pre-fetch & decode secara asinkron segera
        const bufferPromise = this.fetchAndDecodeAudio(text.trim(), voiceChoice);
        this.queue.push({ text: text.trim(), bufferPromise, utteranceId });

        if (!this.isPlaying) {
            this.scheduleNextChunks();
        }
    },

    async scheduleNextChunks() {
        if (this.isPlaying) return;
        this.isPlaying = true;
        state.isSpeaking = true;
        updateUIState('speaking');

        while (this.queue.length > 0) {
            const item = this.queue.shift();
            if (item.utteranceId !== this.currentUtteranceId) break;

            const audioBuffer = await item.bufferPromise;
            if (item.utteranceId !== this.currentUtteranceId) break;

            if (!audioBuffer) {
                // Fallback ke Web Speech jika decode audio gagal
                await this.playWebSpeechFallback(item.text);
                continue;
            }

            const now = state.audioContext.currentTime;
            let startTime = this.nextScheduledTime;

            if (startTime < now) {
                startTime = now + 0.02;
            }

            const sourceNode = state.audioContext.createBufferSource();
            sourceNode.buffer = audioBuffer;

            // Micro-crossfade 25ms per potongan kalimat agar transisi halus tanpa hening/klik
            const fadeGain = state.audioContext.createGain();
            const crossfadeSec = 0.025;
            const dur = audioBuffer.duration;

            fadeGain.gain.setValueAtTime(0.001, startTime);
            fadeGain.gain.linearRampToValueAtTime(1.0, startTime + crossfadeSec);
            if (dur > crossfadeSec * 2) {
                fadeGain.gain.setValueAtTime(1.0, startTime + dur - crossfadeSec);
                fadeGain.gain.linearRampToValueAtTime(0.001, startTime + dur);
            }

            sourceNode.connect(fadeGain);
            fadeGain.connect(state.speakerAnalyser);

            sourceNode.start(startTime);
            this.activeSources.push(sourceNode);

            // Update subtitle tepat saat kalimat mulai bersuara
            const delayMs = Math.max(0, (startTime - now) * 1000);
            setTimeout(() => {
                if (item.utteranceId === this.currentUtteranceId && state.isSpeaking) {
                    setSubtitle(item.text, 'hilmi');
                }
            }, delayMs);

            // Jadwalkan potongan berikutnya dengan overlap crossfade kecil
            this.nextScheduledTime = startTime + dur - crossfadeSec;

            sourceNode.onended = () => {
                const idx = this.activeSources.indexOf(sourceNode);
                if (idx !== -1) this.activeSources.splice(idx, 1);
                if (this.activeSources.length === 0 && this.queue.length === 0 && this.isStreamFinished) {
                    this.isPlaying = false;
                    state.isSpeaking = false;
                    updateUIState('idle');
                }
            };

            // Tunggu jika antrean berikutnya belum selesai di-fetch tapi stream belum beres
            const timeUntilNext = (this.nextScheduledTime - state.audioContext.currentTime) - 0.2;
            if (timeUntilNext > 0.05 && this.queue.length === 0 && !this.isStreamFinished) {
                await new Promise(r => setTimeout(r, Math.min(timeUntilNext * 1000, 200)));
            }
        }

        if (this.queue.length === 0 && this.isStreamFinished && this.activeSources.length === 0) {
            this.isPlaying = false;
            state.isSpeaking = false;
            updateUIState('idle');
        } else if (this.queue.length === 0 && !this.isStreamFinished) {
            this.isPlaying = this.activeSources.length > 0;
        }
    },

    setStreamFinished(fullText) {
        this.isStreamFinished = true;
        if (this.queue.length === 0 && !this.isPlaying && fullText) {
            this.enqueue(fullText);
        } else if (this.queue.length === 0 && this.activeSources.length === 0) {
            this.isPlaying = false;
            state.isSpeaking = false;
            updateUIState('idle');
        }
    },

    playWebSpeechFallback(text) {
        return new Promise(resolve => {
            if (!state.speechSynthesis) return resolve();
            const utt = new SpeechSynthesisUtterance(text);
            utt.lang = 'id-ID';
            utt.rate = 1.0;
            utt.pitch = 1.0;
            if (state.selectedVoice) utt.voice = state.selectedVoice;
            utt.onend = resolve;
            utt.onerror = resolve;
            state.speechSynthesis.speak(utt);
        });
    }
};

// Alias untuk kompatibilitas penuh dengan pemanggil yang sudah ada
const speechQueue = gaplessPlayer;

function speakText(text) {
    if (!text || !text.trim()) return;
    gaplessPlayer.reset(true);
    gaplessPlayer.enqueue(text);
    gaplessPlayer.setStreamFinished(text);
}

function speakTextFallback(text) {
    gaplessPlayer.playWebSpeechFallback(text);
}

// ═══════════════════════════════════════════ AI BRAIN & FALAK LOGIC ═══
async function handleUserQuery(query) {
    if (!query || !query.trim()) return;

    // Reset antrean audio dan batalkan request streaming aktif sebelumnya (Barge-in clean up)
    gaplessPlayer.reset(true);
    if (state.activeAbortController) {
        state.activeAbortController.abort();
    }
    state.activeAbortController = new AbortController();
    const abortSignal = state.activeAbortController.signal;

    state.isThinking = true;
    updateUIState('thinking');
    setSubtitle('Hilmi sedang mengkaji data ephemeris JPL & falak...', 'hilmi');
    addChatBubble(query, 'user');

    // Catat pesan pengguna ke dalam riwayat percakapan
    state.chatHistory.push({ role: 'user', content: query });

    // 1. Coba endpoint streaming SSE untuk respons suara sub-detik
    try {
        const streamResponse = await fetch('/api/assistant/chat/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            signal: abortSignal,
            body: JSON.stringify({ 
                message: query,
                latitude: state.userLocation.lat,
                longitude: state.userLocation.lon,
                date: new Date().toISOString(),
                history: state.chatHistory.slice(-8),
                session_id: 'hilmi_web_session'
            })
        });

        if (streamResponse.ok && streamResponse.body) {
            const reader = streamResponse.body.getReader();
            const decoder = new TextDecoder();
            let fullText = '';
            let sentencesSpoken = 0;
            let sourcesList = [];

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                const chunkStr = decoder.decode(value, { stream: true });
                const lines = chunkStr.split('\n');

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const event = JSON.parse(line.slice(6));
                            if (event.type === 'sentence') {
                                if (event.text && event.text.trim()) {
                                    gaplessPlayer.enqueue(event.text.trim());
                                    sentencesSpoken++;
                                    if (sentencesSpoken === 1) {
                                        setSubtitle(event.text, 'hilmi');
                                    }
                                }
                            } else if (event.type === 'done') {
                                fullText = event.full_text || fullText;
                                sourcesList = event.sources || [];
                                gaplessPlayer.setStreamFinished(fullText);
                            }
                        } catch (err) {}
                    }
                }
            }

            if (fullText) {
                setSubtitle(fullText, 'hilmi');
                addChatBubble(fullText, 'hilmi', sourcesList);
                state.chatHistory.push({ role: 'assistant', content: fullText });
                gaplessPlayer.setStreamFinished(fullText);
                state.isThinking = false;
                return;
            }
        }
    } catch (streamErr) {
        if (streamErr.name === 'AbortError') {
            console.log('[Stream] Permintaan streaming dibatalkan pengguna (Barge-In).');
            return;
        }
        console.warn('Streaming endpoint gagal, beralih ke endpoint standard /api/assistant/chat:', streamErr);
    }

    // 2. Fallback ke endpoint standard /api/assistant/chat
    try {
        const response = await fetch('/api/assistant/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            signal: abortSignal,
            body: JSON.stringify({ 
                message: query,
                latitude: state.userLocation.lat,
                longitude: state.userLocation.lon,
                date: new Date().toISOString(),
                history: state.chatHistory.slice(-8),
                session_id: 'hilmi_web_session'
            }),
            cache: 'no-store'
        });

        if (response.ok) {
            const data = await response.json();
            const reply = data.reply || data.response;
            const sources = data.sources || [];
            setSubtitle(reply, 'hilmi');
            addChatBubble(reply, 'hilmi', sources);
            state.chatHistory.push({ role: 'assistant', content: reply });
            speakText(reply);
            state.isThinking = false;
            return;
        }
    } catch (e) {
        if (e.name === 'AbortError') return;
        console.warn('Backend call failed, using intelligent fallback:', e);
    }

    // Built-in intelligent Fallback
    const clean = query.toLowerCase();
    let reply = '';

    if (clean.includes('mabims') || clean.includes('kriteria')) {
        reply = "Kriteria baru MABIMS 2021 mensyaratkan dua hal: tinggi hilal mar'i minimal 3 derajat dan sudut elongasi geosentris minimal 6,4 derajat saat matahari terbenam.";
    } else if (clean.includes('ramadhan') || clean.includes('puasa') || clean.includes('hilal')) {
        reply = "HILTRON menghitung hisab posisi toposentris hilal saat ijtimak menggunakan ephemeris NASA JPL DE421, lalu dievaluasi berdasarkan kriteria keterlihatan MABIMS dan wujudul hilal.";
    } else if (clean.includes('tracker') || clean.includes('esp32') || clean.includes('teleskop')) {
        reply = "Tracker teleskop HILTRON ditenagai mikrokontroler ESP32 dengan sensor orientasi Bosch BNO055 dan GPS NEO-6M untuk melakukan celestial live lock tracking mengimbangi rotasi bumi.";
    } else if (clean.includes('kiblat')) {
        reply = "Arah kiblat dihitung presisi menggunakan rumus segitiga bola (Spherical Trigonometry) dari koordinat Anda menuju Ka'bah di Makkah.";
    } else {
        reply = `Pertanyaan Anda mengenai "${query}" sangat relevan. Anda dapat memadukan data ephemeris NASA JPL DE421 dengan visualisasi 3D globe dan skydome di platform HILTRON.`;
    }

    setTimeout(() => {
        state.isThinking = false;
        setSubtitle(reply, 'hilmi');
        addChatBubble(reply, 'hilmi');
        speakText(reply);
    }, 500);
}

// ═══════════════════════════════════════════ UI UPDATERS ═══
function setSubtitle(text, speaker = 'hilmi') {
    const subtitleText = document.getElementById('subtitle-text');
    const speakerTag = document.getElementById('subtitle-speaker-tag');
    if (subtitleText) subtitleText.textContent = text;
    if (speakerTag) {
        speakerTag.textContent = speaker === 'user' ? 'Anda' : 'Hilmi (Falak AI)';
        speakerTag.style.color = speaker === 'user' ? 'var(--c-cyan)' : 'var(--c-emerald)';
    }
}

function updateUIState(status) {
    const micBtn = document.getElementById('main-mic-btn');
    const subtitleBox = document.getElementById('subtitle-box');
    const statusText = document.getElementById('status-indicator-text');

    if (!micBtn) return;

    micBtn.classList.remove('listening', 'thinking', 'speaking');
    if (subtitleBox) subtitleBox.classList.remove('listening', 'speaking');

    if (status === 'listening') {
        micBtn.classList.add('listening');
        if (subtitleBox) subtitleBox.classList.add('listening');
        if (statusText) statusText.textContent = 'Mendengarkan...';
    } else if (status === 'thinking') {
        micBtn.classList.add('thinking');
        if (statusText) statusText.textContent = 'Mengkaji Falak...';
    } else if (status === 'speaking') {
        micBtn.classList.add('speaking');
        if (subtitleBox) subtitleBox.classList.add('speaking');
        if (statusText) statusText.textContent = 'Hilmi Berbicara...';
    } else {
        if (statusText) statusText.textContent = 'Siap Berdialog';
    }
}

function addChatBubble(text, sender, sources = []) {
    const container = document.getElementById('chat-messages-container');
    if (!container) return;

    const bubble = document.createElement('div');
    bubble.className = `chat-bubble ${sender}`;

    const textNode = document.createElement('div');
    textNode.textContent = text;
    bubble.appendChild(textNode);

    if (sources && sources.length > 0) {
        const sourcesDiv = document.createElement('div');
        sourcesDiv.className = 'chat-sources';
        sourcesDiv.style.cssText = 'font-size: 0.72rem; opacity: 0.75; margin-top: 6px; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 4px;';

        const label = document.createElement('span');
        label.textContent = '🌐 Rujukan: ';
        sourcesDiv.appendChild(label);

        sources.slice(0, 3).forEach((s, idx) => {
            const a = document.createElement('a');
            a.href = s.uri;
            a.target = '_blank';
            a.rel = 'noopener noreferrer';
            a.textContent = s.title || `[${idx+1}]`;
            a.style.cssText = 'color: var(--c-cyan); text-decoration: underline; margin-right: 8px;';
            sourcesDiv.appendChild(a);
        });
        bubble.appendChild(sourcesDiv);
    }

    container.appendChild(bubble);
    container.scrollTop = container.scrollHeight;
}

// ═══════════════════════════════════════════ WAVEFORM VISUALIZER ═══
function initWaveform() {
    const canvas = document.getElementById('waveform-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let phase = 0;

    function renderWave() {
        requestAnimationFrame(renderWave);
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        const isActive = state.isListening || state.isSpeaking;
        const amplitude = isActive ? 14 : 3;
        const color = state.isListening ? '#EF4444' : (state.isSpeaking ? '#06B6D4' : '#10B981');

        ctx.beginPath();
        ctx.lineWidth = 2.2;
        ctx.strokeStyle = color;

        for (let x = 0; x < canvas.width; x++) {
            const y = (canvas.height / 2) + Math.sin((x * 0.05) + phase) * amplitude * Math.sin(x / canvas.width * Math.PI);
            if (x === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        }

        ctx.stroke();
        phase += isActive ? 0.12 : 0.03;
    }

    renderWave();
}

// ═══════════════════════════════════════════ INITIALIZATION ═══
window.addEventListener('DOMContentLoaded', () => {
    initThreeJS();
    initSpeechRecognition();
    initSpeechSynthesis();
    initWaveform();

    // Browser Geolocation for accurate calculations
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (pos) => {
                state.userLocation.lat = pos.coords.latitude;
                state.userLocation.lon = pos.coords.longitude;
            },
            (err) => console.log('Lokasi default Jakarta:', err.message)
        );
    }

    // Mic button click
    const micBtn = document.getElementById('main-mic-btn');
    if (micBtn) {
        micBtn.addEventListener('click', toggleListening);
    }

    // Toggle Chat History Drawer
    const toggleHistoryBtn = document.getElementById('toggle-history-btn');
    const chatDrawer = document.getElementById('chat-drawer');
    const drawerCloseBtn = document.getElementById('drawer-close-btn');

    if (toggleHistoryBtn && chatDrawer) {
        toggleHistoryBtn.addEventListener('click', () => {
            chatDrawer.classList.toggle('open');
            toggleHistoryBtn.classList.toggle('active');
        });
    }

    if (drawerCloseBtn && chatDrawer) {
        drawerCloseBtn.addEventListener('click', () => {
            chatDrawer.classList.remove('open');
            toggleHistoryBtn?.classList.remove('active');
        });
    }

    // Text Input Form inside Drawer
    const drawerForm = document.getElementById('drawer-input-form');
    if (drawerForm) {
        drawerForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const input = document.getElementById('drawer-query-input');
            if (input && input.value.trim()) {
                const query = input.value.trim();
                input.value = '';
                handleUserQuery(query);
            }
        });
    }

    // Quick Chips
    document.querySelectorAll('.prompt-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            const query = chip.getAttribute('data-prompt') || chip.textContent.trim();
            handleUserQuery(query);
        });
    });

    // Voice Selector change listener & Dynamic Voice Loader
    const voiceSelect = document.getElementById('neural-voice-select');
    if (voiceSelect) {
        voiceSelect.addEventListener('change', (e) => {
            state.selectedNeuralVoice = e.target.value;
            const name = e.target.options[e.target.selectedIndex].text;
            setSubtitle(`"Model suara beralih ke ${name}."`, 'hilmi');
            speakText(`Model suara sekarang menggunakan ${name}.`);
        });

        // Load voices dynamically from backend router
        fetch('/api/assistant/voices')
            .then(res => res.json())
            .then(data => {
                if (data && data.voices && data.voices.length > 0) {
                    voiceSelect.innerHTML = '';
                    data.voices.forEach(v => {
                        const opt = document.createElement('option');
                        opt.value = v.id;
                        opt.textContent = `${v.name} (${v.gender === 'Male' ? 'Pria' : 'Wanita'})`;
                        if (v.id === state.selectedNeuralVoice) opt.selected = true;
                        voiceSelect.appendChild(opt);
                    });
                }
            })
            .catch(() => {});
    }
});
