import * as THREE from 'three';

/* ═══════════════════════════════════════════════════════════════
   FalakHub · Skydome.js
   Full 24-hour sky cycle GLSL shader.
   Celestial positions are ABSOLUTE — driven entirely by ephemeris
   data from the FastAPI backend. NO dt-based fake rotation.
═══════════════════════════════════════════════════════════════ */

export function initSkydome(container, labelsContainer) {
    if (!container) return null;

    const scene    = new THREE.Scene();
    const aspect   = container.clientWidth / container.clientHeight;
    let   fov      = 60;
    const camera   = new THREE.PerspectiveCamera(fov, aspect, 0.1, 20000);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    renderer.toneMapping         = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.0;
    container.appendChild(renderer.domElement);

    // ── Shared state ─────────────────────────────────────────────
    const SKY_RADIUS = 1000;
    const domLabels  = [];

    // Current simulation values (set by updateSimulation)
    let curSunAlt = -10;  // degrees
    let curSunAz  = 270;
    let curMoonAlt = 5;
    let curMoonAz  = 285;
    let curIllumination = 0.1;

    // ── Alt/Az → World 3D (inside-out hemisphere, camera at origin) ─
    function altAzToVec3(altDeg, azDeg, r = SKY_RADIUS) {
        const alt = THREE.MathUtils.degToRad(altDeg);
        const az  = THREE.MathUtils.degToRad(azDeg);
        return new THREE.Vector3(
             r * Math.cos(alt) * Math.sin(az),
             r * Math.sin(alt),
            -r * Math.cos(alt) * Math.cos(az)
        );
    }

    // ── Full 24h Sky Shader ───────────────────────────────────────
    // sunAltNorm: -1 (midnight) → 0 (horizon) → +1 (noon)
    const skyMat = new THREE.ShaderMaterial({
        uniforms: {
            sunAltNorm:  { value: -0.1 },  // -1..+1
            moonAltNorm: { value:  0.05 },
            illumination:{ value:  0.1  },
        },
        side: THREE.BackSide,
        depthWrite: false,
        vertexShader: `
            varying vec3 vWorldDir;
            void main() {
                vWorldDir = normalize((modelMatrix * vec4(position, 0.0)).xyz);
                gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
            }
        `,
        fragmentShader: `
            uniform float sunAltNorm;
            uniform float moonAltNorm;
            uniform float illumination;
            varying vec3 vWorldDir;

            // ── Palette definitions ──────────────────────────────
            // Zenith colors at various sun altitudes
            vec3 zenithNight()    { return vec3(0.012, 0.015, 0.045); }
            vec3 zenithTwilight() { return vec3(0.05,  0.04,  0.15);  }
            vec3 zenithDay()      { return vec3(0.08,  0.28,  0.65);  }

            // Horizon colors
            vec3 horizonNight()   { return vec3(0.02,  0.03,  0.08);  }
            vec3 horizonGolden()  { return vec3(0.90,  0.45,  0.05);  }  // sunrise/set
            vec3 horizonDay()     { return vec3(0.55,  0.75,  0.95);  }
            vec3 horizonDusk()    { return vec3(0.30,  0.10,  0.25);  }  // civil twilight

            void main() {
                float h = normalize(vWorldDir).y; // -1 (ground) → +1 (zenith)
                float t = clamp(h, 0.0, 1.0);     // horizon blend weight

                // ── Sun phase ────────────────────────────────────
                // sunAltNorm: -1=night, 0=horizon, +1=noon
                float s = clamp(sunAltNorm, -1.0, 1.0);

                // Zenith color interpolation
                vec3 zenith;
                if (s < -0.05) {
                    // Night → civil twilight
                    float f = smoothstep(-1.0, -0.05, s);
                    zenith  = mix(zenithNight(), zenithTwilight(), f);
                } else if (s < 0.15) {
                    // Twilight → early day
                    float f = smoothstep(-0.05, 0.15, s);
                    zenith  = mix(zenithTwilight(), zenithDay(), f);
                } else {
                    zenith = zenithDay();
                }

                // Horizon color
                vec3 horizon;
                if (s < -0.12) {
                    horizon = horizonNight();
                } else if (s < -0.04) {
                    float f = smoothstep(-0.12, -0.04, s);
                    horizon = mix(horizonNight(), horizonDusk(), f);
                } else if (s < 0.04) {
                    // Sunrise / Sunset golden hour
                    float f = smoothstep(-0.04, 0.04, s);
                    horizon = mix(horizonDusk(), horizonGolden(), f);
                } else if (s < 0.15) {
                    float f = smoothstep(0.04, 0.15, s);
                    horizon = mix(horizonGolden(), horizonDay(), f);
                } else {
                    horizon = horizonDay();
                }

                // Sky gradient: horizon → zenith
                // Use a power curve for realistic Rayleigh falloff
                float blend = pow(t, 0.5);
                vec3 skyCol = mix(horizon, zenith, blend);

                // ── Golden horizon band near sun altitude ────────
                float sunNear = clamp(1.0 - abs(s) * 8.0, 0.0, 1.0);
                float hBand   = clamp(1.0 - h * 6.0, 0.0, 1.0);
                skyCol += vec3(0.5, 0.2, 0.0) * sunNear * hBand * 0.4;

                // ── Night: blue-purple glow at horizon ───────────
                if (s < -0.05) {
                    float nightH = clamp(1.0 - h * 4.0, 0.0, 1.0);
                    skyCol += vec3(0.01, 0.02, 0.08) * nightH * clamp(-s * 2.0, 0.0, 1.0);
                }

                // ── Moon glow contribution at horizon ────────────
                if (moonAltNorm > 0.0 && s < 0.0) {
                    float moonH  = clamp(1.0 - h * 10.0, 0.0, 1.0);
                    float moonGl = moonAltNorm * illumination * 0.25;
                    skyCol += vec3(0.12, 0.14, 0.20) * moonGl * moonH;
                }

                // ── Ground (below horizon) ───────────────────────
                if (h < 0.0) {
                    skyCol = mix(skyCol, vec3(0.005, 0.007, 0.012), clamp(-h * 6.0, 0.0, 1.0));
                }

                gl_FragColor = vec4(skyCol, 1.0);
            }
        `
    });

    const skyDome = new THREE.Mesh(new THREE.SphereGeometry(SKY_RADIUS, 32, 24), skyMat);
    scene.add(skyDome);

    // ── Ground Plane ─────────────────────────────────────────────
    const groundMat = new THREE.MeshBasicMaterial({ color: 0x020508, side: THREE.DoubleSide });
    const groundMesh = new THREE.Mesh(new THREE.PlaneGeometry(SKY_RADIUS * 4, SKY_RADIUS * 4), groundMat);
    groundMesh.rotation.x = -Math.PI / 2;
    groundMesh.position.y = -1.5;
    scene.add(groundMesh);

    // ── Horizon Circle ────────────────────────────────────────────
    const horizonPts = [];
    for (let i = 0; i <= 360; i += 3) horizonPts.push(altAzToVec3(0, i, SKY_RADIUS * 0.98));
    const horizonGeom = new THREE.BufferGeometry().setFromPoints(horizonPts);
    scene.add(new THREE.Line(horizonGeom, new THREE.LineBasicMaterial({
        color: 0x10B981, transparent: true, opacity: 0.4, depthWrite: false
    })));

    // ── Altitude Grid Lines ───────────────────────────────────────
    [15, 30, 45, 60, 75].forEach(alt => {
        const pts = [];
        for (let az = 0; az <= 360; az += 4) pts.push(altAzToVec3(alt, az, SKY_RADIUS * 0.97));
        const geom = new THREE.BufferGeometry().setFromPoints(pts);
        scene.add(new THREE.Line(geom, new THREE.LineBasicMaterial({
            color: 0x1e3a5f, transparent: true, opacity: 0.25, depthWrite: false
        })));
    });

    // ── Stars (visible at night) ──────────────────────────────────
    const STAR_COUNT = 2500;
    const starPos    = new Float32Array(STAR_COUNT * 3);
    for (let i = 0; i < STAR_COUNT; i++) {
        let alt, az;
        do { alt = (Math.random() * 180) - 90; } while (alt < -5);
        az = Math.random() * 360;
        const v = altAzToVec3(alt, az, SKY_RADIUS * 0.9);
        starPos[i*3]   = v.x;
        starPos[i*3+1] = v.y;
        starPos[i*3+2] = v.z;
    }
    const starGeom = new THREE.BufferGeometry();
    starGeom.setAttribute('position', new THREE.BufferAttribute(starPos, 3));
    const starMat = new THREE.PointsMaterial({
        color: 0xffffff, size: 1.2, sizeAttenuation: true,
        transparent: true, opacity: 0, depthWrite: false
    });
    const stars = new THREE.Points(starGeom, starMat);
    scene.add(stars);

    // ── Sun Mesh ──────────────────────────────────────────────────
    const sunGeom = new THREE.SphereGeometry(14, 24, 24);
    const sunMat  = new THREE.MeshBasicMaterial({ color: 0xFFF5B6 });
    const sunMesh = new THREE.Mesh(sunGeom, sunMat);
    scene.add(sunMesh);
    // Sun glow halo (additive)
    const glowGeom = new THREE.SphereGeometry(22, 16, 16);
    const glowMat  = new THREE.MeshBasicMaterial({
        color: 0xFFBB44, transparent: true, opacity: 0.12,
        side: THREE.BackSide, blending: THREE.AdditiveBlending, depthWrite: false
    });
    sunMesh.add(new THREE.Mesh(glowGeom, glowMat));

    // Sun directional light
    const sunLight = new THREE.DirectionalLight(0xFFEECC, 2.0);
    scene.add(sunLight);
    scene.add(new THREE.AmbientLight(0x112244, 0.4));

    // ── Moon Mesh ─────────────────────────────────────────────────
    const moonGeom    = new THREE.SphereGeometry(10, 32, 32);
    const moonTexture = new THREE.TextureLoader().load(
        'https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/textures/planets/moon_1024.jpg',
        () => renderer.render(scene, camera)
    );
    const moonMat  = new THREE.MeshStandardMaterial({
        map: moonTexture, roughness: 1.0, metalness: 0.0
    });
    const moonMesh = new THREE.Mesh(moonGeom, moonMat);
    scene.add(moonMesh);

    // Moon receives light from the sun's direction
    sunLight.target = moonMesh;

    // ── Labels ────────────────────────────────────────────────────
    function addLabel(pos, text, className, tracked = null) {
        const el = document.createElement('div');
        el.className  = className;
        el.innerText  = text;
        labelsContainer.appendChild(el);
        const entry = { el, pos: pos.clone(), tracked };
        domLabels.push(entry);
        return entry;
    }

    addLabel(altAzToVec3(0,   0, SKY_RADIUS * 0.88), 'U', 'compass-label');
    addLabel(altAzToVec3(0,  90, SKY_RADIUS * 0.88), 'T', 'compass-label');
    addLabel(altAzToVec3(0, 180, SKY_RADIUS * 0.88), 'S', 'compass-label');
    addLabel(altAzToVec3(0, 270, SKY_RADIUS * 0.88), 'B', 'compass-label');

    const sunLabel  = addLabel(sunMesh.position,  '☀ MATAHARI', 'astro-label sun-label',  sunMesh);
    const moonLabel = addLabel(moonMesh.position, '☽ HILAL',    'astro-label moon-label', moonMesh);
    sunLabel.el.style.display  = 'block';
    moonLabel.el.style.display = 'block';

    // ARCL / ARCV measurement labels
    const arclLabel = addLabel(new THREE.Vector3(), '', 'measurement-label');
    const arcvLabel = addLabel(new THREE.Vector3(), '', 'measurement-label');
    arclLabel.el.style.display = 'block';
    arcvLabel.el.style.display = 'block';

    // ── Measurement Lines ─────────────────────────────────────────
    const lineMat  = (color) => new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.8, depthWrite: false });
    const arclLine = new THREE.Line(new THREE.BufferGeometry(), lineMat(0x38bdf8));
    const arcvLine = new THREE.Line(new THREE.BufferGeometry(), lineMat(0xFCD34D));
    const dazLine  = new THREE.Line(new THREE.BufferGeometry(), lineMat(0xa78bfa));
    scene.add(arclLine); scene.add(arcvLine); scene.add(dazLine);

    // ── Camera Mouse Control ──────────────────────────────────────
    let lookLon  = 270;
    let lookLat  = 10;
    let dragging = false;
    let prevMouse = { x: 0, y: 0 };

    function updateCameraLook() {
        camera.lookAt(altAzToVec3(lookLat, lookLon, 100));
    }

    container.addEventListener('mousedown', (e) => {
        dragging  = true;
        prevMouse = { x: e.clientX, y: e.clientY };
        e.stopPropagation();
    });
    document.addEventListener('mouseup', () => { dragging = false; });
    container.addEventListener('mousemove', (e) => {
        if (!dragging) return;
        const zf = fov / 60;
        lookLon -= (e.clientX - prevMouse.x) * 0.22 * zf;
        lookLat += (e.clientY - prevMouse.y) * 0.22 * zf;
        lookLat  = Math.max(-20, Math.min(85, lookLat));
        prevMouse = { x: e.clientX, y: e.clientY };
        updateCameraLook();
    });
    container.addEventListener('wheel', (e) => {
        e.preventDefault(); e.stopPropagation();
        fov = Math.max(5, Math.min(100, fov + e.deltaY * 0.04));
        camera.fov = fov;
        camera.updateProjectionMatrix();
    }, { passive: false });

    // Touch support
    let lastTouchDist = null;
    container.addEventListener('touchstart', (e) => {
        if (e.touches.length === 1) {
            dragging  = true;
            prevMouse = { x: e.touches[0].clientX, y: e.touches[0].clientY };
        } else if (e.touches.length === 2) {
            lastTouchDist = Math.hypot(
                e.touches[0].clientX - e.touches[1].clientX,
                e.touches[0].clientY - e.touches[1].clientY
            );
        }
        e.preventDefault();
    }, { passive: false });
    container.addEventListener('touchmove', (e) => {
        if (e.touches.length === 1 && dragging) {
            const zf = fov / 60;
            lookLon -= (e.touches[0].clientX - prevMouse.x) * 0.22 * zf;
            lookLat += (e.touches[0].clientY - prevMouse.y) * 0.22 * zf;
            lookLat  = Math.max(-20, Math.min(85, lookLat));
            prevMouse = { x: e.touches[0].clientX, y: e.touches[0].clientY };
            updateCameraLook();
        } else if (e.touches.length === 2 && lastTouchDist !== null) {
            const d = Math.hypot(
                e.touches[0].clientX - e.touches[1].clientX,
                e.touches[0].clientY - e.touches[1].clientY
            );
            fov = Math.max(5, Math.min(100, fov - (d - lastTouchDist) * 0.15));
            lastTouchDist = d;
            camera.fov = fov; camera.updateProjectionMatrix();
        }
        e.preventDefault();
    }, { passive: false });
    container.addEventListener('touchend', () => { dragging = false; lastTouchDist = null; });

    // ── Label Updater ─────────────────────────────────────────────
    function updateLabels() {
        const rect = container.getBoundingClientRect();
        const tmp  = new THREE.Vector3();
        domLabels.forEach(({ el, pos, tracked }) => {
            if (tracked) tmp.copy(tracked.position);
            else          tmp.copy(pos);

            tmp.project(camera);

            // Hide if behind camera
            if (tmp.z > 1) { el.style.display = 'none'; return; }

            const x = ( tmp.x * 0.5 + 0.5) * rect.width;
            const y = (-tmp.y * 0.5 + 0.5) * rect.height;
            el.style.display = 'block';
            el.style.left    = `${x}px`;
            el.style.top     = `${y}px`;
        });
    }

    // ── Fullscreen ────────────────────────────────────────────────
    const fsBtn = document.getElementById('btn-skydome-fs');
    const wrapper = document.getElementById('skydome-wrapper');
    if (fsBtn && wrapper) {
        fsBtn.addEventListener('click', () => {
            if (!document.fullscreenElement) wrapper.requestFullscreen?.();
            else document.exitFullscreen?.();
        });
    }

    // ── Resize Observer ───────────────────────────────────────────
    const resizeObs = new ResizeObserver(() => {
        const w = container.clientWidth;
        const h = container.clientHeight;
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
        renderer.setSize(w, h);
    });
    resizeObs.observe(container);

    // ── Render Loop ───────────────────────────────────────────────
    function animate() {
        requestAnimationFrame(animate);
        updateLabels();
        renderer.render(scene, camera);
    }
    updateCameraLook();
    animate();

    // ── Public API ────────────────────────────────────────────────
    return {
        updateSimulation(appState) {
            const { baseSunAlt, baseSunAz, baseMoonAlt, baseMoonAz,
                    timeOffsetMinutes, baseArcl, illumination } = appState;

            // ── Interpolate alt/az with time offset ───────────────
            // 0.25 deg/min altitude drop (approx 15°/hour)
            // 0.25 deg/min azimuth change
            const offsetH  = timeOffsetMinutes / 60;
            const sunAlt   = baseSunAlt  - offsetH * 15;
            const sunAz    = baseSunAz   + offsetH * 15;
            const moonAlt  = baseMoonAlt - offsetH * 14.5;
            const moonAz   = baseMoonAz  + offsetH * 14.5;

            curSunAlt  = sunAlt;
            curSunAz   = sunAz;
            curMoonAlt = moonAlt;
            curMoonAz  = moonAz;
            curIllumination = illumination ?? 0.05;

            // ── Absolute positional update ────────────────────────
            const sunPos  = altAzToVec3(sunAlt,  sunAz,  SKY_RADIUS * 0.9);
            const moonPos = altAzToVec3(moonAlt, moonAz, SKY_RADIUS * 0.9);

            sunMesh.position.copy(sunPos);
            moonMesh.position.copy(moonPos);
            sunLight.position.copy(sunPos);

            // ── Sky shader uniforms ───────────────────────────────
            const sunNorm = THREE.MathUtils.clamp(sunAlt / 90, -1, 1);
            skyMat.uniforms.sunAltNorm.value   = sunNorm;
            skyMat.uniforms.moonAltNorm.value  = THREE.MathUtils.clamp(moonAlt / 90, -1, 1);
            skyMat.uniforms.illumination.value = curIllumination;

            // ── Stars: fade in when sun below horizon ─────────────
            const starOpacity = THREE.MathUtils.clamp((-sunAlt - 2) / 10, 0, 0.9);
            starMat.opacity = starOpacity;

            // ── Sun visibility ────────────────────────────────────
            sunMesh.visible = sunAlt > -5;
            sunLight.intensity = sunAlt > 0
                ? THREE.MathUtils.lerp(0, 2.5, Math.min(sunAlt / 30, 1))
                : 0;

            // ── Moon: phase shader (illuminate crescent) ──────────
            moonMesh.visible = moonAlt > -3;
            // Rotate moon so lit hemisphere faces the sun direction
            if (moonMesh.visible) {
                moonMesh.lookAt(sunPos);
            }

            // ── ARCL line: Sun → Moon ─────────────────────────────
            arclLine.geometry.setFromPoints([sunPos, moonPos]);

            // ── ARCV: Moon vertical drop to sun altitude ──────────
            const cornerPos = altAzToVec3(sunAlt, moonAz, SKY_RADIUS * 0.9);
            arcvLine.geometry.setFromPoints([moonPos, cornerPos]);
            dazLine.geometry.setFromPoints([cornerPos, sunPos]);

            // ── Measurement label positions ───────────────────────
            arclLabel.pos.copy(sunPos).lerp(moonPos, 0.5);
            arcvLabel.pos.copy(moonPos).lerp(cornerPos, 0.5);
            const arcv = moonAlt - sunAlt;
            arclLabel.el.textContent = `ARCL: ${baseArcl?.toFixed(2) ?? '—'}°`;
            arcvLabel.el.textContent = `ARCV: ${arcv.toFixed(2)}°`;
        },

        resetCamera() {
            lookLon = 270; lookLat = 10; fov = 60;
            camera.fov = fov; camera.updateProjectionMatrix(); updateCameraLook();
        },
    };
}
