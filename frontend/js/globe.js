import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { Lensflare, LensflareElement } from 'three/addons/objects/Lensflare.js';

/* ═══════════════════════════════════════════════════════════════
   FalakHub · Globe.js
   Photorealistic Earth with Lensflare Sun, textured Moon,
   on-demand rendering, and absolute ephemeris positioning.
═══════════════════════════════════════════════════════════════ */

// ── Procedural Lensflare Texture Generator ─────────────────────
function makeFlareTexture(size = 256, color = '#ffffff') {
    const c = document.createElement('canvas');
    c.width = c.height = size;
    const ctx = c.getContext('2d');
    const half = size / 2;
    const g = ctx.createRadialGradient(half, half, 0, half, half, half);
    g.addColorStop(0,    color);
    g.addColorStop(0.12, color.replace('1)', '0.8)').replace('#', 'rgba(255,255,255,'));
    g.addColorStop(0.4,  'rgba(255,240,200,0.15)');
    g.addColorStop(1,    'rgba(0,0,0,0)');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, size, size);
    const tex = new THREE.CanvasTexture(c);
    return tex;
}

function makeHexFlare(size = 128) {
    const c = document.createElement('canvas');
    c.width = c.height = size;
    const ctx = c.getContext('2d');
    const half = size / 2;
    ctx.save();
    ctx.translate(half, half);
    ctx.rotate(Math.PI / 6);
    ctx.beginPath();
    for (let i = 0; i < 6; i++) {
        const a = (i / 6) * Math.PI * 2;
        ctx[i === 0 ? 'moveTo' : 'lineTo'](Math.cos(a) * half * 0.7, Math.sin(a) * half * 0.7);
    }
    ctx.closePath();
    const g = ctx.createRadialGradient(0, 0, 0, 0, 0, half * 0.7);
    g.addColorStop(0,   'rgba(200,220,255,0.6)');
    g.addColorStop(0.5, 'rgba(150,180,255,0.2)');
    g.addColorStop(1,   'rgba(0,0,0,0)');
    ctx.fillStyle = g;
    ctx.fill();
    ctx.restore();
    return new THREE.CanvasTexture(c);
}

export function initGlobe(container, cities, onCitySelect) {

    // ── Scene ────────────────────────────────────────────────────
    const scene = new THREE.Scene();
    scene.background = new THREE.Color('#050912');
    scene.fog = new THREE.FogExp2('#050912', 0.0015);

    // ── Camera ───────────────────────────────────────────────────
    const camera = new THREE.PerspectiveCamera(
        45,
        container.clientWidth / container.clientHeight,
        0.1,
        5000
    );
    camera.position.set(0, 8, 28);

    // ── Renderer (on-demand) ─────────────────────────────────────
    const renderer = new THREE.WebGLRenderer({
        antialias: true,
        powerPreference: 'high-performance',
        logarithmicDepthBuffer: true,
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.1;
    renderer.shadowMap.enabled = false; // off — not needed, saves bandwidth
    container.appendChild(renderer.domElement);

    // On-demand rendering flag
    let needsRender = true;
    function requestRender() { needsRender = true; }

    // ── Controls ─────────────────────────────────────────────────
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor  = 0.06;
    controls.minDistance    = 10;
    controls.maxDistance    = 120;
    controls.enablePan      = false;
    controls.rotateSpeed    = 0.5;
    controls.zoomSpeed      = 0.8;
    controls.addEventListener('change', requestRender);
    controls.addEventListener('start',  () => { isCameraFollowing = false; requestRender(); });

    // ── Texture Loader ───────────────────────────────────────────
    const loader = new THREE.TextureLoader();
    const loadTex = (url, onLoad) => {
        loader.load(url, (t) => { t.colorSpace = THREE.SRGBColorSpace; requestRender(); if(onLoad) onLoad(t); }, undefined, () => {});
        return loader.load(url);
    };

    // ── Stars ────────────────────────────────────────────────────
    const starCount = 6000;
    const starPositions = new Float32Array(starCount * 3);
    const starSizes = new Float32Array(starCount);
    for (let i = 0; i < starCount; i++) {
        const theta = Math.random() * Math.PI * 2;
        const phi   = Math.acos(2 * Math.random() - 1);
        const r     = 600 + Math.random() * 400;
        starPositions[i*3]   = r * Math.sin(phi) * Math.cos(theta);
        starPositions[i*3+1] = r * Math.sin(phi) * Math.sin(theta);
        starPositions[i*3+2] = r * Math.cos(phi);
        starSizes[i] = Math.random() * 1.5 + 0.3;
    }
    const starGeom = new THREE.BufferGeometry();
    starGeom.setAttribute('position', new THREE.BufferAttribute(starPositions, 3));
    starGeom.setAttribute('size',     new THREE.BufferAttribute(starSizes, 1));
    const starMat = new THREE.PointsMaterial({
        color:       0xffffff,
        size:        0.6,
        sizeAttenuation: true,
        transparent: true,
        opacity:     0.85,
        depthWrite:  false,
    });
    scene.add(new THREE.Points(starGeom, starMat));

    // ── Earth ────────────────────────────────────────────────────
    const EARTH_RADIUS = 6.371;
    const earthGeom = new THREE.SphereGeometry(EARTH_RADIUS, 72, 72);

    // Textures (NASA/public-domain via Three.js repo CDN)
    const earthDayTex     = loadTex('https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/textures/planets/earth_atmos_2048.jpg');
    const earthNightTex   = loadTex('https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/textures/planets/earth_lights_2048.png');
    const earthNormalTex  = loadTex('https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/textures/planets/earth_normal_2048.jpg');

    const earthMat = new THREE.MeshStandardMaterial({
        map:          earthDayTex,
        normalMap:    earthNormalTex,
        normalScale:  new THREE.Vector2(0.6, 0.6),
        emissiveMap:  earthNightTex,
        emissive:     new THREE.Color(0x334466),
        emissiveIntensity: 0.6,
        roughness:    0.75,
        metalness:    0.05,
    });

    const earthMesh = new THREE.Mesh(earthGeom, earthMat);
    earthMesh.name = 'Earth';

    // Atmosphere glow
    const atmGeom = new THREE.SphereGeometry(EARTH_RADIUS * 1.025, 48, 48);
    const atmMat  = new THREE.MeshPhongMaterial({
        color:       0x4488ff,
        transparent: true,
        opacity:     0.08,
        side:        THREE.FrontSide,
        depthWrite:  false,
    });
    const atmosphere = new THREE.Mesh(atmGeom, atmMat);
    earthMesh.add(atmosphere);

    // Thin rim glow (additive blend)
    const rimGeom = new THREE.SphereGeometry(EARTH_RADIUS * 1.04, 48, 48);
    const rimMat  = new THREE.MeshPhongMaterial({
        color:       0x2255cc,
        transparent: true,
        opacity:     0.04,
        side:        THREE.BackSide,
        depthWrite:  false,
        blending:    THREE.AdditiveBlending,
    });
    earthMesh.add(new THREE.Mesh(rimGeom, rimMat));

    // Earth container: separates Earth's rotation from orbital/scene positioning
    const earthContainer = new THREE.Group();
    earthContainer.add(earthMesh);
    scene.add(earthContainer);

    // ── Marker Group (attached to Earth) ─────────────────────────
    const markerGroup = new THREE.Group();
    earthMesh.add(markerGroup);

    // Convert lat/lon to 3D Cartesian on the Earth sphere
    function latLonToVec3(lat, lon, radius = EARTH_RADIUS) {
        const phi   = (90 - lat)  * (Math.PI / 180);
        const theta = (lon + 180) * (Math.PI / 180);
        return new THREE.Vector3(
            -(radius * Math.sin(phi) * Math.cos(theta)),
             (radius * Math.cos(phi)),
             (radius * Math.sin(phi) * Math.sin(theta))
        );
    }

    // Pin mesh factory
    function makePinMesh(color = 0xF59E0B) {
        const g = new THREE.SphereGeometry(0.13, 12, 12);
        const m = new THREE.MeshBasicMaterial({ color });
        const mesh = new THREE.Mesh(g, m);
        // Halo ring around pin
        const ringG = new THREE.RingGeometry(0.18, 0.23, 24);
        const ringM = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.5, side: THREE.DoubleSide });
        const ring  = new THREE.Mesh(ringG, ringM);
        mesh.add(ring);
        return mesh;
    }

    // Seed initial city markers
    cities.forEach((city, idx) => {
        const pin = makePinMesh(0xF59E0B);
        pin.position.copy(latLonToVec3(city.lat, city.lon));
        pin.lookAt(pin.position.clone().multiplyScalar(2));
        pin.userData = { idx };
        markerGroup.add(pin);
    });

    let activeMarker3D = markerGroup.children[0];
    if (activeMarker3D) activeMarker3D.material.color.setHex(0x10B981);

    // Public: add a new marker from geocode result
    function addMarker(lat, lon, label = '') {
        const pin = makePinMesh(0xA78BFA);
        pin.position.copy(latLonToVec3(lat, lon));
        pin.lookAt(pin.position.clone().multiplyScalar(2));
        const idx = cities.length - 1; // most recently pushed
        pin.userData = { idx, label };
        markerGroup.add(pin);
        requestRender();
        return pin;
    }

    // ── Lighting ─────────────────────────────────────────────────
    const ambientLight = new THREE.AmbientLight(0x112244, 0.5);
    scene.add(ambientLight);

    // Sun directional light — position updated with ephemeris
    const sunLight = new THREE.DirectionalLight(0xFFEECC, 2.8);
    sunLight.position.set(120, 0, 0);
    scene.add(sunLight);

    // Fill light (opposite side — simulates reflected light from space)
    const fillLight = new THREE.DirectionalLight(0x223355, 0.15);
    fillLight.position.set(-80, 30, -80);
    scene.add(fillLight);

    // ── Sun (Lensflare) ───────────────────────────────────────────
    const flareTex0 = makeFlareTexture(256, 'rgba(255,240,180,1)');
    const flareTex1 = makeFlareTexture(128, 'rgba(255,200,100,1)');
    const hexTex    = makeHexFlare(128);

    // Small emissive core
    const sunCoreGeom = new THREE.SphereGeometry(0.6, 16, 16);
    const sunCoreMat  = new THREE.MeshBasicMaterial({ color: 0xFFFFEE });
    const sunMesh     = new THREE.Mesh(sunCoreGeom, sunCoreMat);
    scene.add(sunMesh);

    // Lensflare
    const lensflare = new Lensflare();
    lensflare.addElement(new LensflareElement(flareTex0, 600, 0,  new THREE.Color(1, 0.92, 0.7)));
    lensflare.addElement(new LensflareElement(flareTex1, 160, 0.4, new THREE.Color(1, 0.7,  0.3)));
    lensflare.addElement(new LensflareElement(hexTex,    80,  0.7, new THREE.Color(0.5, 0.7, 1.0)));
    lensflare.addElement(new LensflareElement(flareTex1, 50,  0.9, new THREE.Color(0.8, 0.4, 1.0)));
    lensflare.addElement(new LensflareElement(flareTex0, 30,  1.0, new THREE.Color(1, 0.5, 0.2)));
    sunMesh.add(lensflare);

    // ── Moon ─────────────────────────────────────────────────────
    const MOON_RADIUS  = 1.737;  // scaled similarly to earth
    const moonGeom     = new THREE.SphereGeometry(MOON_RADIUS, 48, 48);
    const moonTex      = loadTex('https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/textures/planets/moon_1024.jpg');
    const moonBumpTex  = loader.load('https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/textures/planets/moon_1024.jpg'); // reuse as bump (real bump map same CDN)
    const moonMat      = new THREE.MeshStandardMaterial({
        map:       moonTex,
        bumpMap:   moonBumpTex,
        bumpScale: 0.5,
        roughness: 1.0,
        metalness: 0.0,
    });
    const moonMesh = new THREE.Mesh(moonGeom, moonMat);
    moonMesh.name  = 'Moon';
    scene.add(moonMesh); // Scene-level: positioned in world space via ephemeris

    // ── Orbit Trace Lines ─────────────────────────────────────────
    function buildOrbitCircle(radius, segments = 128) {
        const pts = [];
        for (let i = 0; i <= segments; i++) {
            const a = (i / segments) * Math.PI * 2;
            pts.push(new THREE.Vector3(Math.cos(a) * radius, 0, Math.sin(a) * radius));
        }
        const geom = new THREE.BufferGeometry().setFromPoints(pts);
        return geom;
    }

    const sunOrbitGeom = buildOrbitCircle(120);
    const sunOrbitLine = new THREE.LineLoop(
        sunOrbitGeom,
        new THREE.LineBasicMaterial({ color: 0x443322, transparent: true, opacity: 0.25, depthWrite: false })
    );
    scene.add(sunOrbitLine);

    const moonOrbitGeom = buildOrbitCircle(18);
    const moonOrbitLine = new THREE.LineLoop(
        moonOrbitGeom,
        new THREE.LineBasicMaterial({ color: 0x334455, transparent: true, opacity: 0.35, depthWrite: false })
    );
    scene.add(moonOrbitLine);

    // Reorient orbit ring so it passes through a given world position
    function tiltOrbitToPoint(orbitLine, targetPos) {
        const flat = new THREE.Vector3(0, 1, 0); // original orbit normal is Y
        const dir  = targetPos.clone().normalize();
        if (dir.lengthSq() < 0.0001) return;
        // Find the rotation axis (cross of Y and dir)
        const axis = flat.clone().cross(dir);
        if (axis.lengthSq() < 0.0001) return;
        const angle = Math.acos(THREE.MathUtils.clamp(flat.dot(dir), -1, 1));
        orbitLine.setRotationFromAxisAngle(axis.normalize(), angle);
    }

    // ── MABIMS Map: InstancedMesh ─────────────────────────────────
    let mabimsInstance = null;
    const dotGeom = new THREE.SphereGeometry(0.06, 4, 4);
    const colorGreen  = new THREE.Color(0x10B981);
    const colorBlue   = new THREE.Color(0x3B82F6);
    const colorRed    = new THREE.Color(0xEF4444);

    function drawMabimsMap(geojson) {
        if (!geojson?.features?.length) return;
        if (mabimsInstance) { earthMesh.remove(mabimsInstance); mabimsInstance.geometry.dispose(); }

        const count = geojson.features.length;
        mabimsInstance = new THREE.InstancedMesh(dotGeom, new THREE.MeshBasicMaterial({ vertexColors: true }), count);
        mabimsInstance.name = 'MabimsMap';

        const dummy  = new THREE.Object3D();
        const colors = new Float32Array(count * 3);
        geojson.features.forEach((feat, i) => {
            const [lon, lat] = feat.geometry.coordinates;
            dummy.position.copy(latLonToVec3(lat, lon, EARTH_RADIUS + 0.06));
            dummy.lookAt(dummy.position.clone().multiplyScalar(2));
            dummy.updateMatrix();
            mabimsInstance.setMatrixAt(i, dummy.matrix);

            const col = feat.properties?.color === '#10B981' ? colorGreen
                      : feat.properties?.color === '#3B82F6' ? colorBlue
                      : colorRed;
            colors[i*3]   = col.r;
            colors[i*3+1] = col.g;
            colors[i*3+2] = col.b;
        });
        mabimsInstance.geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
        mabimsInstance.instanceMatrix.needsUpdate = true;
        earthMesh.add(mabimsInstance);
        requestRender();
    }

    // ── Raycaster ─────────────────────────────────────────────────
    const raycaster  = new THREE.Raycaster();
    const mouse      = new THREE.Vector2();
    const tooltip    = document.getElementById('coords-tooltip');
    let   isPointerDown = false;
    let   pointerDownPos = { x: 0, y: 0 };

    function getMouseNDC(e) {
        const rect = container.getBoundingClientRect();
        return new THREE.Vector2(
            ((e.clientX - rect.left) / rect.width)  * 2 - 1,
            -((e.clientY - rect.top)  / rect.height) * 2 + 1
        );
    }

    // Hover — show tooltip
    let hoverRAF = null;
    renderer.domElement.addEventListener('pointermove', (e) => {
        if (hoverRAF) cancelAnimationFrame(hoverRAF);
        hoverRAF = requestAnimationFrame(() => {
            mouse.copy(getMouseNDC(e));
            raycaster.setFromCamera(mouse, camera);
            const hits = raycaster.intersectObject(earthMesh);
            if (hits.length > 0) {
                const local = earthMesh.worldToLocal(hits[0].point.clone());
                const sph   = new THREE.Spherical().setFromVector3(local);
                const lat   = 90 - THREE.MathUtils.radToDeg(sph.phi);
                let   lon   = THREE.MathUtils.radToDeg(sph.theta) - 180;
                if (lon < -180) lon += 360;
                if (lon >  180) lon -= 360;
                const latStr = `${Math.abs(lat).toFixed(2)}°${lat >= 0 ? 'N' : 'S'}`;
                const lonStr = `${Math.abs(lon).toFixed(2)}°${lon >= 0 ? 'E' : 'W'}`;
                if (tooltip) {
                    document.getElementById('coords-tooltip-text').textContent = `${latStr}, ${lonStr}`;
                    tooltip.style.display  = 'block';
                    tooltip.style.left     = `${e.clientX}px`;
                    tooltip.style.top      = `${e.clientY}px`;
                }
                renderer.domElement.style.cursor = 'crosshair';
            } else {
                if (tooltip) tooltip.style.display = 'none';
                renderer.domElement.style.cursor = 'grab';
            }
        });
    });

    renderer.domElement.addEventListener('pointerdown', (e) => {
        isPointerDown   = true;
        pointerDownPos  = { x: e.clientX, y: e.clientY };
    });

    renderer.domElement.addEventListener('pointerup', (e) => {
        if (!isPointerDown) return;
        isPointerDown = false;
        // Only register as click if pointer didn't drag
        const dx = e.clientX - pointerDownPos.x;
        const dy = e.clientY - pointerDownPos.y;
        if (Math.sqrt(dx*dx + dy*dy) > 6) return;

        mouse.copy(getMouseNDC(e));
        raycaster.setFromCamera(mouse, camera);

        // Check markers first
        const markerHits = raycaster.intersectObjects(markerGroup.children, true);
        if (markerHits.length > 0) {
            const obj = markerHits[0].object;
            const pin = obj.parent?.userData?.idx !== undefined ? obj.parent : obj;
            if (pin.userData.idx !== undefined) {
                onCitySelect(pin.userData.idx);
                return;
            }
        }

        // Then check Earth surface
        const earthHits = raycaster.intersectObject(earthMesh);
        if (earthHits.length > 0) {
            const local = earthMesh.worldToLocal(earthHits[0].point.clone());
            const sph   = new THREE.Spherical().setFromVector3(local);
            const lat   = 90 - THREE.MathUtils.radToDeg(sph.phi);
            let   lon   = THREE.MathUtils.radToDeg(sph.theta) - 180;
            if (lon < -180) lon += 360;
            if (lon >  180) lon -= 360;
            if (window.onMapClick) window.onMapClick(lat, lon);
        }
    });

    renderer.domElement.addEventListener('pointerleave', () => {
        if (tooltip) tooltip.style.display = 'none';
    });

    // ── State ─────────────────────────────────────────────────────
    let targetEarthAngle = 0;
    let isCameraFollowing = false;
    let targetCameraPos   = new THREE.Vector3();
    let camPanTarget      = null; // for smooth pan

    const targetSunPos  = new THREE.Vector3(120, 0, 0);
    const targetMoonPos = new THREE.Vector3(18, 0, 0);

    // Celestial Coordinates (RA/Dec) to World Space
    // RA is in hours (0-24), Dec is in degrees.
    // Earth rotates by GMST around Y axis.
    // RA=0 matches -X in world space when GMST=0.
    function raDecToVec3(raHours, decDeg, radius) {
        const ra  = THREE.MathUtils.degToRad(raHours * 15);
        const dec = THREE.MathUtils.degToRad(decDeg);
        const y = radius * Math.sin(dec);
        const rXZ = radius * Math.cos(dec);
        const x = -rXZ * Math.cos(ra);
        const z = -rXZ * Math.sin(ra);
        return new THREE.Vector3(x, y, z);
    }

    // ── Animate Loop (on-demand) ──────────────────────────────────
    const clock = new THREE.Clock();

    function animate() {
        requestAnimationFrame(animate);
        const dt = clock.getDelta();

        // Smooth Earth rotation toward GMST target
        const angleDiff = targetEarthAngle - earthMesh.rotation.y;
        if (Math.abs(angleDiff) > 0.0005) {
            earthMesh.rotation.y += angleDiff * Math.min(dt * 3, 0.08);
            needsRender = true;
        }

        // Smooth Sun position lerp
        const sunDist = sunMesh.position.distanceToSquared(targetSunPos);
        if (sunDist > 0.01) {
            sunMesh.position.lerp(targetSunPos, Math.min(dt * 3, 0.08));
            sunLight.position.copy(sunMesh.position);
            needsRender = true;
        }

        // Smooth Moon position lerp
        const moonDist = moonMesh.position.distanceToSquared(targetMoonPos);
        if (moonDist > 0.01) {
            moonMesh.position.lerp(targetMoonPos, Math.min(dt * 3, 0.08));
            needsRender = true;
        }

        // Smooth camera pan to new location
        if (camPanTarget) {
            camera.position.lerp(camPanTarget, Math.min(dt * 2, 0.06));
            if (camera.position.distanceToSquared(camPanTarget) < 0.1) camPanTarget = null;
            controls.update();
            needsRender = true;
        }

        // Following active marker
        if (isCameraFollowing && activeMarker3D) {
            const wp = new THREE.Vector3();
            activeMarker3D.getWorldPosition(wp);
            targetCameraPos.copy(wp).normalize().multiplyScalar(22);
            camera.position.lerp(targetCameraPos, Math.min(dt * 2, 0.06));
            controls.update();
            needsRender = true;
        }

        controls.update();

        if (needsRender) {
            renderer.render(scene, camera);
            needsRender = false;
        }
    }
    animate();

    // ── Resize Handler ────────────────────────────────────────────
    const resizeObs = new ResizeObserver(() => {
        const w = container.clientWidth;
        const h = container.clientHeight;
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
        renderer.setSize(w, h);
        requestRender();
    });
    resizeObs.observe(container);

    // ── Public API ────────────────────────────────────────────────
    return {

        focusCity(idx) {
            activeMarker3D = markerGroup.children.find(m => m.userData.idx === idx);
            isCameraFollowing = true;
            camPanTarget = null;
            markerGroup.children.forEach(m => m.material.color.setHex(0xF59E0B));
            if (activeMarker3D) activeMarker3D.material.color.setHex(0x10B981);
            requestRender();
        },

        addMarker(lat, lon) {
            return addMarker(lat, lon);
        },

        panToLatLon(lat, lon) {
            const worldPos = latLonToVec3(lat, lon, EARTH_RADIUS);
            // Compute camera offset: position above the point
            const dir = worldPos.clone().normalize();
            camPanTarget = dir.multiplyScalar(22);
            isCameraFollowing = false;
            requestRender();
        },

        setEphemeris(gmst_hours, sun_ra, sun_dec, moon_ra, moon_dec) {
            // Absolute Earth rotation from GMST
            targetEarthAngle = (gmst_hours / 24) * Math.PI * 2 + Math.PI;

            // Absolute Sun position from RA/Dec
            targetSunPos.copy(raDecToVec3(sun_ra, sun_dec, 120));

            // Absolute Moon position from RA/Dec
            targetMoonPos.copy(raDecToVec3(moon_ra, moon_dec, 18));

            // Reorient orbit guide rings
            tiltOrbitToPoint(sunOrbitLine,  targetSunPos);
            tiltOrbitToPoint(moonOrbitLine, targetMoonPos);

            requestRender();
        },

        drawMabimsMap(geojson) {
            drawMabimsMap(geojson);
        },
    };
}
