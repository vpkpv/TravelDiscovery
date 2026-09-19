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
#   # or, to avoid retyping every var by hand each time (and risking one
#   # getting silently dropped — GEMINI_API_KEY has gone missing this way
#   # more than once, with no error anywhere, just a feature quietly doing
#   # nothing): cp deploy-env.sh.example deploy-env.sh, fill in your real
#   # values (gitignored, never commit it), then:
#   #   source deploy-env.sh && ./deploy.sh
#   # optionally: REGION=us-central1 GOOGLE_PLACES_API_KEY=... PROJECT_ID=... ./deploy.sh
#   # for Spotify OAuth: also set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET
#   # (from developer.spotify.com/dashboard) — this script computes and wires
#   # up SPOTIFY_REDIRECT_URI itself. See api/.env.example for details,
#   # including the Dev Mode user-allowlisting requirement.
#   # for Firebase Auth + the closed-pilot approval gate: set AUTH_ENABLED=true
#   # plus FIREBASE_API_KEY, FIREBASE_AUTH_DOMAIN, FIREBASE_PROJECT_ID,
#   # FIREBASE_APP_ID (from the Firebase console's web app config). See
#   # api/.env.example for the full setup, including the IAM role the
#   # travel-api service account needs for Firestore access.
#   # to also stand up the MCP server (exposes picks to Claude/other MCP
#   # clients — see api/mcp_server.py): set DEPLOY_MCP=true. Needs
#   # AUTH_ENABLED=true too, since that's how a user gets a token to
#   # authenticate to it (POST /api/tokens).
#   # to also stand up periodic re-ingestion (keeps Firestore venue data
#   # refreshed without a manual local `python -m ingest.run`): set
#   # DEPLOY_INGEST_JOB=true, needs AUTH_ENABLED=true (that's what makes
#   # ingest.run write to Firestore instead of only a local output.json) and
#   # GEMINI_API_KEY. Optionally INGEST_SCHEDULE (cron, default weekly) and
#   # SUPADATA_API_KEY. Every firing re-runs the full curated VIDEOS list in
#   # api/ingest/run.py — real Gemini/Places/Supadata API cost each time.
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
  --set-env-vars "GOOGLE_PLACES_API_KEY=${GOOGLE_PLACES_API_KEY:-},GEMINI_API_KEY=${GEMINI_API_KEY:-},GEMINI_MODEL=${GEMINI_MODEL:-},SPOTIFY_CLIENT_ID=${SPOTIFY_CLIENT_ID:-},SPOTIFY_CLIENT_SECRET=${SPOTIFY_CLIENT_SECRET:-},AUTH_ENABLED=${AUTH_ENABLED:-}"

API_URL=$(gcloud run services describe travel-api --region "$REGION" --format='value(status.url)')
echo "API live at: $API_URL"

echo "== Deploying web =="
gcloud run deploy travel-web \
  --source ./web \
  --region "$REGION" \
  --allow-unauthenticated \
  --set-env-vars "API_URL=${API_URL},FIREBASE_API_KEY=${FIREBASE_API_KEY:-},FIREBASE_AUTH_DOMAIN=${FIREBASE_AUTH_DOMAIN:-},FIREBASE_PROJECT_ID=${FIREBASE_PROJECT_ID:-},FIREBASE_APP_ID=${FIREBASE_APP_ID:-}"

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

if [ "${AUTH_ENABLED:-}" = "true" ]; then
  echo
  echo "Auth: make sure the travel-api service account has Firestore access"
  echo "(Cloud Datastore User role, at minimum) — see api/.env.example."
  echo "Approve yourself: add a document at approved_users/<your-uid> in the"
  echo "Firestore console (Firebase console -> Firestore -> Start collection)"
  echo "after signing in once so a uid exists to approve."
fi

MCP_URL=""
if [ "${DEPLOY_MCP:-}" = "true" ]; then
  echo
  echo "== Deploying MCP server =="
  gcloud run deploy travel-mcp \
    --source ./api \
    --region "$REGION" \
    --allow-unauthenticated \
    --set-env-vars "ASGI_APP=mcp_server:app,AUTH_ENABLED=${AUTH_ENABLED:-},GOOGLE_PLACES_API_KEY=${GOOGLE_PLACES_API_KEY:-},GEMINI_API_KEY=${GEMINI_API_KEY:-},GEMINI_MODEL=${GEMINI_MODEL:-},MCP_ISSUER_URL=${API_URL}"

  MCP_URL=$(gcloud run services describe travel-mcp --region "$REGION" --format='value(status.url)')

  # --allow-unauthenticated here is deliberate, not an oversight: Cloud
  # Run's own IAM auth and this server's bearer-token auth are two
  # different layers — requiring both would mean an external MCP client
  # also needs a Google Cloud identity token, which defeats the point of
  # the simpler personal-access-token scheme chosen for this.
  gcloud run services update travel-mcp \
    --region "$REGION" \
    --update-env-vars "MCP_RESOURCE_URL=${MCP_URL}" \
    >/dev/null

  echo "MCP server live at: ${MCP_URL}/mcp"
  if [ "${AUTH_ENABLED:-}" != "true" ]; then
    echo "Warning: DEPLOY_MCP=true but AUTH_ENABLED isn't 'true' — POST"
    echo "${API_URL}/api/tokens will 404, so there's no way to mint a token"
    echo "to authenticate to this server. Set both together."
  else
    echo "Also needs Firestore access on travel-mcp's service account, same"
    echo "as travel-api above (they can share the role grant if it's the"
    echo "same service account, which it is by default)."
  fi
fi

if [ "${DEPLOY_INGEST_JOB:-}" = "true" ]; then
  echo
  echo "== Deploying ingest job + scheduler =="
  gcloud services enable run.googleapis.com cloudscheduler.googleapis.com

  # Cloud Run Jobs run to completion instead of serving traffic, which is
  # what a batch re-ingest needs — a Service would just sit there between
  # runs. --command/--args override the image's default uvicorn CMD without
  # needing a separate Dockerfile.
  gcloud run jobs deploy travel-ingest \
    --source ./api \
    --region "$REGION" \
    --command python3 \
    --args="-m,ingest.run" \
    --max-retries 0 \
    --task-timeout 3600 \
    --set-env-vars "GEMINI_API_KEY=${GEMINI_API_KEY:-},GEMINI_MODEL=${GEMINI_MODEL:-},GOOGLE_PLACES_API_KEY=${GOOGLE_PLACES_API_KEY:-},SUPADATA_API_KEY=${SUPADATA_API_KEY:-},AUTH_ENABLED=${AUTH_ENABLED:-}"

  JOB_SA=$(gcloud run jobs describe travel-ingest --region "$REGION" --format='value(template.template.serviceAccount)')
  if [ -z "$JOB_SA" ]; then
    JOB_SA=$(gcloud iam service-accounts list --filter="displayName:'Default compute service account'" --format='value(email)' | head -n1)
  fi

  SCHEDULER_SA="travel-ingest-scheduler@${PROJECT_ID}.iam.gserviceaccount.com"
  if ! gcloud iam service-accounts describe "$SCHEDULER_SA" >/dev/null 2>&1; then
    gcloud iam service-accounts create travel-ingest-scheduler \
      --display-name "Triggers the travel-ingest Cloud Run Job on a schedule"
  fi
  gcloud run jobs add-iam-policy-binding travel-ingest \
    --region "$REGION" \
    --member "serviceAccount:${SCHEDULER_SA}" \
    --role "roles/run.invoker" \
    >/dev/null

  INGEST_SCHEDULE="${INGEST_SCHEDULE:-0 3 * * 1}"  # weekly, Monday 3am UTC
  JOB_RUN_URI="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/travel-ingest:run"

  if gcloud scheduler jobs describe travel-ingest-schedule --location "$REGION" >/dev/null 2>&1; then
    gcloud scheduler jobs update http travel-ingest-schedule \
      --location "$REGION" \
      --schedule "$INGEST_SCHEDULE" \
      --uri "$JOB_RUN_URI" \
      --http-method POST \
      --oauth-service-account-email "$SCHEDULER_SA" \
      >/dev/null
  else
    gcloud scheduler jobs create http travel-ingest-schedule \
      --location "$REGION" \
      --schedule "$INGEST_SCHEDULE" \
      --uri "$JOB_RUN_URI" \
      --http-method POST \
      --oauth-service-account-email "$SCHEDULER_SA" \
      >/dev/null
  fi

  echo "Ingest job 'travel-ingest' deployed, scheduled '$INGEST_SCHEDULE' (UTC) via 'travel-ingest-schedule'."
  echo "Run it once by hand right now with:"
  echo "  gcloud run jobs execute travel-ingest --region $REGION"
  if [ -n "$JOB_SA" ]; then
    echo "Make sure ${JOB_SA} has the Cloud Datastore User role (same as travel-api) so it can write to Firestore."
  fi
  if [ "${AUTH_ENABLED:-}" != "true" ]; then
    echo "Warning: DEPLOY_INGEST_JOB=true but AUTH_ENABLED isn't 'true' — each run will"
    echo "produce output.json inside the ephemeral job container and then discard it,"
    echo "since there's nowhere durable to write it without Firestore. Set both together."
  fi
fi

echo
echo "======================================================"
echo "API:  $API_URL"
echo "Web:  $WEB_URL"
if [ -n "$MCP_URL" ]; then
  echo "MCP:  ${MCP_URL}/mcp"
fi
if [ "${DEPLOY_INGEST_JOB:-}" = "true" ]; then
  echo "Ingest job: travel-ingest (scheduled: ${INGEST_SCHEDULE})"
fi
echo "======================================================"
echo
echo "Open the web URL above — that's the app."
echo
echo "Optional hardening: lock the API down to only accept requests from the"
echo "web app's origin (right now it accepts any origin):"
echo "  gcloud run services update travel-api --region $REGION \\"
echo "    --update-env-vars ALLOWED_ORIGINS=$WEB_URL"
