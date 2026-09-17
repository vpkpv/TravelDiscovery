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

export const spotifyLoginUrl = `${BASE}/auth/spotify/login`;

// /api/photo proxies Places photos server-side (see main.py) so the
// Places API key never reaches the browser. Not behind auth — an <img>
// tag can't attach a Bearer header — see that endpoint's docstring.
export const photoUrl = (ref, w = 400) =>
  `${BASE}/api/photo?ref=${encodeURIComponent(ref)}&w=${w}`;

export const api = {
  me: () => get('/api/me'),
  cuisines: () => get('/api/cuisines'),
  musicGenres: () => get('/api/music-genres'),
  cities: ({ q = '', visited = [] } = {}) =>
    get(`/api/cities?q=${encodeURIComponent(q)}&visited=${visited.join(',')}`),
  results: ({ city, filter = 'all', musicGenre = '' }) =>
    get(`/api/results?city=${encodeURIComponent(city)}&filter=${filter}&music_genre=${encodeURIComponent(musicGenre)}`),
  surprise: ({ city, seed = 0, musicGenre = '' }) =>
    get(`/api/results/surprise?city=${encodeURIComponent(city)}&seed=${seed}&music_genre=${encodeURIComponent(musicGenre)}`),
};
