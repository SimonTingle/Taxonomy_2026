# syntax=docker/dockerfile:1
#
# Multi-stage build:
#   1. classify  -> run the Python pipeline, produce classified.csv + summary.json
#   2. web        -> build the React review UI with that data baked into /public
#   3. runtime    -> nginx serving the static UI
#
# Build against the real export:
#   docker build --build-arg INPUT_CSV=Book1.csv -t taxonomy-review .
# Falls back to data/sample_export.csv if the given file is absent.

# ---- 1. classify ----------------------------------------------------------
FROM python:3.12-slim AS classify
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY taxonomy/ taxonomy/
COPY data/ data/
# Bring in the (optional) real export; keep the copy tolerant if it's absent.
COPY . .
ARG INPUT_CSV=data/sample_export.csv
RUN set -e; \
    IN="$INPUT_CSV"; \
    [ -f "$IN" ] || { echo "WARN: $IN not found, using sample"; IN=data/sample_export.csv; }; \
    python -m taxonomy.cli --input "$IN" --out /out; \
    ls -la /out

# ---- 2. web build ---------------------------------------------------------
FROM node:20-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json* ./
RUN npm ci 2>/dev/null || npm install
COPY web/ ./
# Bake the generated data so the UI auto-loads it (no backend needed at runtime).
COPY --from=classify /out/classified.csv /out/summary.json ./public/
RUN npm run build

# ---- 3. runtime -----------------------------------------------------------
FROM nginx:alpine AS runtime
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=web /web/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD wget -qO- http://localhost/health || exit 1
CMD ["nginx", "-g", "daemon off;"]
