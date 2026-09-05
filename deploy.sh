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
set -euo pipefail

: "${PROJECT_ID:?Set PROJECT_ID, e.g. PROJECT_ID=my-project ./deploy.sh}"
REGION="${REGION:-us-central1}"

gcloud config set project "$PROJECT_ID"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com

echo "== Deploying API =="
gcloud run deploy travel-api \
  --source ./api \
  --region "$REGION" \
  --allow-unauthenticated \
  --set-env-vars "GOOGLE_PLACES_API_KEY=${GOOGLE_PLACES_API_KEY:-}"

API_URL=$(gcloud run services describe travel-api --region "$REGION" --format='value(status.url)')
echo "API live at: $API_URL"

echo "== Deploying web =="
gcloud run deploy travel-web \
  --source ./web \
  --region "$REGION" \
  --allow-unauthenticated \
  --set-env-vars "API_URL=${API_URL}"

WEB_URL=$(gcloud run services describe travel-web --region "$REGION" --format='value(status.url)')

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
