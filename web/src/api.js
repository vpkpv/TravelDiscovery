const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

async function get(path) {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json();
}

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
