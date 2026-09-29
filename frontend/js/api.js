export const API_BASE = "https://3eb766dd4c8729.lhr.life/api";
export async function fetchEphemeris(lat, lon, date) {
    try {
        const res = await fetch(`${API_BASE}/ephemeris?lat=${lat}&lon=${lon}&date=${date}`);
        if (!res.ok) throw new Error("API Error");
        return await res.json();
    } catch (e) {
        console.error(e);
        return null;
    }
}

export async function fetchMabimsMap(date) {
    try {
        const res = await fetch(`${API_BASE}/map/mabims?date=${date}`);
        if (!res.ok) throw new Error("API Error");
        const buffer = await res.arrayBuffer();

        // Decode geobuf
        // geobuf and Pbf are globally available from unpkg imports in index.html
        const pbf = new Pbf(new Uint8Array(buffer));
        const geojson = geobuf.decode(pbf);
        return geojson;
    } catch (e) {
        console.error(e);
        return null;
    }
}

export async function fetchGeocode(query) {
    try {
        const res = await fetch(`${API_BASE}/search?q=${encodeURIComponent(query)}`);
        if (!res.ok) throw new Error("Location not found");
        return await res.json();
    } catch (e) {
        console.error(e);
        return null;
    }
}
