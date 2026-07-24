# Deployment

The runtime artifact is a single **nginx image** serving the React review UI with the
classified data (`classified.csv` + `summary.json`) baked in at build time. No backend
service runs in production — classification happens during the Docker build.

Build against the real export with `--build-arg INPUT_CSV=Book1.csv`
(falls back to `data/sample_export.csv` if the file is missing).

---

## CapRover

CapRover reads [`captain-definition`](../captain-definition) → [`Dockerfile`](../Dockerfile).

**Option A — deploy from the CLI (tarball upload):**
```bash
npm i -g caprover
caprover login                     # point at your CapRover instance
caprover deploy                    # uploads this folder, builds on the server
```

**Option B — deploy from Git:** in the CapRover dashboard, create an app and connect
this repo; CapRover builds on push.

**Passing the real CSV:** the export must be in the build context.
Because `Book1.csv` is git-ignored, a Git-based deploy will fall back to the sample.
To ship the real data, either:
- deploy via `caprover deploy` (tarball includes the working tree, incl. `Book1.csv`), **or**
- set a build arg in the CapRover app config → *Deployment* → build args: `INPUT_CSV=Book1.csv`.

CapRover maps the container's port 80 to the app automatically and terminates TLS for you.
The healthcheck hits `/health`.

---

## Docker Swarm

```bash
# 1. init a swarm (once, on the manager node)
docker swarm init

# 2. build the image (choose the input CSV)
docker build --build-arg INPUT_CSV=Book1.csv -t taxonomy-review:latest .

# 3. deploy the stack
IMAGE=taxonomy-review:latest PUBLISHED_PORT=8080 REPLICAS=2 \
  docker stack deploy -c docker-compose.yml taxonomy

# 4. check it
docker stack services taxonomy
curl -s localhost:8080/health      # -> ok
```

The [`docker-compose.yml`](../docker-compose.yml) `deploy:` block sets 2 replicas,
rolling `start-first` updates with automatic rollback, restart-on-failure, resource
limits, and an overlay network — all honoured by `docker stack deploy`.

**Multi-node note:** on a multi-node swarm, build and push the image to a registry the
workers can pull, and set `IMAGE` to that reference:
```bash
docker build --build-arg INPUT_CSV=Book1.csv -t registry.example.com/taxonomy-review:latest .
docker push registry.example.com/taxonomy-review:latest
IMAGE=registry.example.com/taxonomy-review:latest docker stack deploy -c docker-compose.yml taxonomy
```

Tear down: `docker stack rm taxonomy`.

---

## Refreshing the data

The data is a build-time snapshot. To publish updated classifications, re-run the build
(new `INPUT_CSV` or updated `taxonomy/rules.yaml`) and redeploy. If you need to swap data
without rebuilding, mount a volume over `/usr/share/nginx/html` containing a fresh
`classified.csv` / `summary.json` and the built assets.
