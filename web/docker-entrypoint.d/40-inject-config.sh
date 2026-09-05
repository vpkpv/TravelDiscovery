#!/bin/sh
# nginx's official entrypoint auto-runs every executable script here before
# starting nginx. This overwrites the no-op public/config.js (already baked
# into the image at /usr/share/nginx/html/config.js) with the real API_URL
# from the Cloud Run env var — so one built image can point at any backend
# without rebuilding.
set -e
envsubst '${API_URL}' < /etc/nginx/templates/config.js.template > /usr/share/nginx/html/config.js
