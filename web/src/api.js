// In production, window.__API_URL__ is injected at container startup (see
// web/docker-entrypoint.d and web/config.js.template) so the same built
// image can point at whatever API URL a deploy sets, without rebuilding.
// Local dev falls through to VITE_API_URL (build-time) or localhost.
const BASE = window.__API_URL__ || import.meta.env.VITE_API_URL || 'http://localhost:8000';

async function get(path) {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json();
}

export const spotifyLoginUrl = `${BASE}/auth/spotify/login`;

export const api = {
  cuisines: () => get('/api/cuisines'),
  musicGenres: () => get('/api/music-genres'),
  cities: ({ q = '', visited = [] } = {}) =>
    get(`/api/cities?q=${encodeURIComponent(q)}&visited=${visited.join(',')}`),
  results: ({ city, filter = 'all' }) =>
    get(`/api/results?city=${encodeURIComponent(city)}&filter=${filter}`),
  surprise: ({ city, seed = 0 }) =>
    get(`/api/results/surprise?city=${encodeURIComponent(city)}&seed=${seed}`),
};
