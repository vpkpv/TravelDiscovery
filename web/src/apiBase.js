// Split out from api.js so firebase.js can also use this without a
// circular import (api.js imports getIdToken from firebase.js, so
// firebase.js importing BASE back from api.js would be circular).
export const API_BASE = window.__API_URL__ || import.meta.env.VITE_API_URL || 'http://localhost:8000';
