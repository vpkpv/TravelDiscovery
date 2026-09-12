#!/usr/bin/env bash
# Deploys api/ and web/ to Cloud Run as two separate services.
#
# Requires: gcloud CLI installed and authenticated (`gcloud init` /
# `gcloud auth login`) as an account with permission on the target project.
# No local Docker needed — `gcloud run deploy --source` builds remotely via
# Cloud Build.
#
# Usage:
#   PROJECT_ID=your-gcp-project-id ./deploy.sh
#   # optionally: REGION=us-central1 GOOGLE_PLACES_API_KEY=... PROJECT_ID=... ./deploy.sh
#   # for Spotify OAuth: also set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET
#   # (from developer.spotify.com/dashboard) — this script computes and wires
#   # up SPOTIFY_REDIRECT_URI itself. See api/.env.example for details,
#   # including the Dev Mode user-allowlisting requirement.
set -euo pipefail

: "${PROJECT_ID:?Set PROJECT_ID, e.g. PROJECT_ID=my-project ./deploy.sh}"
REGION="${REGION:-us-central1}"

gcloud config set project "$PROJECT_ID"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com

if [ -s ./api/ingest/output.json ]; then
  echo "Found api/ingest/output.json — ingested venues will be included in this deploy."
else
  echo "No api/ingest/output.json found — deploying with curated Lisbon data only."
  echo "  Run 'python -m ingest.run' from api/ first if you want ingested cities (e.g. Mumbai) included."
fi

echo "== Deploying API =="
gcloud run deploy travel-api \
  --source ./api \
  --region "$REGION" \
  --allow-unauthenticated \
  --set-env-vars "GOOGLE_PLACES_API_KEY=${GOOGLE_PLACES_API_KEY:-},SPOTIFY_CLIENT_ID=${SPOTIFY_CLIENT_ID:-},SPOTIFY_CLIENT_SECRET=${SPOTIFY_CLIENT_SECRET:-}"

API_URL=$(gcloud run services describe travel-api --region "$REGION" --format='value(status.url)')
echo "API live at: $API_URL"

echo "== Deploying web =="
gcloud run deploy travel-web \
  --source ./web \
  --region "$REGION" \
  --allow-unauthenticated \
  --set-env-vars "API_URL=${API_URL}"

WEB_URL=$(gcloud run services describe travel-web --region "$REGION" --format='value(status.url)')

# SPOTIFY_REDIRECT_URI/WEB_URL depend on URLs only known after both services
# exist, so wire them onto travel-api now via --update-env-vars (merges,
# unlike --set-env-vars above which would wipe the vars just set).
SPOTIFY_REDIRECT_URI="${API_URL}/auth/spotify/callback"
gcloud run services update travel-api \
  --region "$REGION" \
  --update-env-vars "WEB_URL=${WEB_URL},SPOTIFY_REDIRECT_URI=${SPOTIFY_REDIRECT_URI}" \
  >/dev/null

if [ -n "${SPOTIFY_CLIENT_ID:-}" ]; then
  echo
  echo "Spotify: make sure this exact Redirect URI is registered on your"
  echo "Spotify app (developer.spotify.com/dashboard -> your app -> Settings):"
  echo "  $SPOTIFY_REDIRECT_URI"
fi

echo
echo "======================================================"
echo "API:  $API_URL"
echo "Web:  $WEB_URL"
echo "======================================================"
echo
echo "Open the web URL above — that's the app."
echo
echo "Optional hardening: lock the API down to only accept requests from the"
echo "web app's origin (right now it accepts any origin):"
echo "  gcloud run services update travel-api --region $REGION \\"
echo "    --update-env-vars ALLOWED_ORIGINS=$WEB_URL"
