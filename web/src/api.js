// In production, window.__API_URL__ is injected at container startup (see
// web/docker-entrypoint.d and web/config.js.template) so the same built
// image can point at whatever API URL a deploy sets, without rebuilding.
// Local dev falls through to VITE_API_URL (build-time) or localhost.
const BASE = window.__API_URL__ || import.meta.env.VITE_API_URL || 'http://localhost:8000';

import { getIdToken } from './firebase.js';

async function get(path) {
  const token = await getIdToken();
  const headers = token ? { Authorization: `Bearer ${token}` } : {};
  const res = await fetch(`${BASE}${path}`, { headers });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json();
}

async function post(path, body) {
  const token = await getIdToken();
  const headers = { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) };
  const res = await fetch(`${BASE}${path}`, { method: 'POST', headers, body: JSON.stringify(body) });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json();
}

async function put(path, body) {
  const token = await getIdToken();
  const headers = { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) };
  const res = await fetch(`${BASE}${path}`, { method: 'PUT', headers, body: JSON.stringify(body) });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json();
}

async function del(path) {
  const token = await getIdToken();
  const headers = token ? { Authorization: `Bearer ${token}` } : {};
  const res = await fetch(`${BASE}${path}`, { method: 'DELETE', headers });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json();
}

export const spotifyLoginUrl = `${BASE}/auth/spotify/login`;

// /api/photo proxies Places photos server-side (see main.py) so the
// Places API key never reaches the browser. Not behind auth — an <img>
// tag can't attach a Bearer header — see that endpoint's docstring.
export const photoUrl = (ref, w = 400) =>
  `${BASE}/api/photo?ref=${encodeURIComponent(ref)}&w=${w}`;

export const api = {
  me: () => get('/api/me'),
  getPrefs: () => get('/api/prefs'),
  savePrefs: (prefs) => post('/api/prefs', { prefs }),
  cuisines: () => get('/api/cuisines'),
  musicGenres: () => get('/api/music-genres'),
  cities: ({ q = '', visited = [] } = {}) =>
    get(`/api/cities?q=${encodeURIComponent(q)}&visited=${visited.join(',')}`),
  results: ({ city, filter = 'all', musicGenre = '', chefs = [], cuisines = [], tripId = '' }) =>
    get(`/api/results?city=${encodeURIComponent(city)}&filter=${filter}&music_genre=${encodeURIComponent(musicGenre)}&chefs=${encodeURIComponent(chefs.join(','))}&cuisines=${encodeURIComponent(cuisines.join(','))}&trip_id=${encodeURIComponent(tripId)}`),
  surprise: ({ city, seed = 0, musicGenre = '', chefs = [], cuisines = [] }) =>
    get(`/api/results/surprise?city=${encodeURIComponent(city)}&seed=${seed}&music_genre=${encodeURIComponent(musicGenre)}&chefs=${encodeURIComponent(chefs.join(','))}&cuisines=${encodeURIComponent(cuisines.join(','))}`),
  // Cross-device saved picks (see api/main.py's /api/saved) — a browsable
  // history across cities/trips, not the purely-local toggle this used to
  // be (see ResultsFeed.jsx).
  getSaved: () => get('/api/saved'),
  saveItem: (id, item) => put(`/api/saved/${encodeURIComponent(id)}`, { item }),
  deleteItem: (id) => del(`/api/saved/${encodeURIComponent(id)}`),
  // Trip planning (see api/main.py's /api/trips, users/{uid}/trips).
  getTrips: () => get('/api/trips'),
  createTrip: (trip) => post('/api/trips', trip),
  getTrip: (id) => get(`/api/trips/${encodeURIComponent(id)}`),
  updateTrip: (id, trip) => put(`/api/trips/${encodeURIComponent(id)}`, trip),
  deleteTrip: (id) => del(`/api/trips/${encodeURIComponent(id)}`),
  setAnchorEvent: (tripId, anchor) => put(`/api/trips/${encodeURIComponent(tripId)}/anchor`, anchor),
  clearAnchorEvent: (tripId) => del(`/api/trips/${encodeURIComponent(tripId)}/anchor`),
};
