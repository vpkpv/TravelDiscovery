FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8080
EXPOSE 8080

# ASGI_APP picks which app this container serves — main:app (the API, the
# default) or mcp_server:app (the MCP server) — so both Cloud Run services
# (travel-api, travel-mcp) can share this one image/source dir. See
# deploy.sh.
CMD exec uvicorn ${ASGI_APP:-main:app} --host 0.0.0.0 --port ${PORT}
