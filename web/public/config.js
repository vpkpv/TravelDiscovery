// No-op for local dev — api.js falls through to VITE_API_URL / localhost.
// In production this exact file path is overwritten at container startup
// (see docker-entrypoint.d/40-inject-config.sh) with the real API URL, so
// the same built image works against whatever backend a deploy points it at.
