# Document Taxonomy & Type Classifier

Classifies a SharePoint file export (~120k files) into a **Department → Function → Document Type**
taxonomy, inferring the document *type* from the file name and folder path, with a per-file
**confidence score**. Built for reviewing and refining a taxonomy before applying it back to SharePoint.

## What it does

1. **Ingest** — loads the export CSV and auto-detects the filename/path columns from common
   SharePoint headers (`FileLeafRef`, `FileRef`, `Name`, `Path`, …). Override with flags if needed.
2. **Parse path** — normalises separators, strips the `/sites/<Site>/` container, splits folders into levels.
3. **Classify doc type** — a rule engine (name keywords > path keywords > extension) assigns a document
   type + confidence. Rules live in [`taxonomy/rules.yaml`](taxonomy/rules.yaml) — **edit that file to refine**, no code changes.
4. **Map taxonomy** — top folder levels → Department / Function (configurable), with raw-folder fallback.
5. **Output** — `out/classified.csv` (every file + taxonomy + confidence) and `out/summary.json`
   (type/department counts, common path structures, low-confidence count).
6. **Review UI** — a React app to browse, filter, and eyeball low-confidence rows.

## Quick start

```bash
./run.sh            # bootstrap venv, classify Book1.csv (or the sample), stage UI data
./run.sh --serve    # same, then launch the review UI at http://localhost:5173
```

## Backend

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m taxonomy.cli --input data/sample_export.csv --out out/
# real export (headerless 2-col files are auto-detected; override if needed):
python -m taxonomy.cli -i Book1.csv -o out/ --filename-col col_0 --path-col col_1

pytest -q          # run tests
```

Ingest auto-detects both **headered** SharePoint exports (`FileLeafRef`, `FileRef`, …) and
**headerless** 2-column `filename,path` files (like `Book1.csv`), including a UTF-8 BOM.

## Review UI

```bash
# copy the latest outputs so the UI auto-loads them
cp out/classified.csv out/summary.json web/public/

cd web
npm install
npm run dev        # http://localhost:5173
```

The UI also has a file-upload box, so you can drop a `classified.csv` in directly without copying.

## Deployment

The production artifact is a single nginx image serving the React UI with the classified
data baked in — see [`deploy/DEPLOY.md`](deploy/DEPLOY.md) for **CapRover** and **Docker Swarm**.

```bash
docker build --build-arg INPUT_CSV=Book1.csv -t taxonomy-review:latest .
docker run -p 8080:80 taxonomy-review:latest      # http://localhost:8080
```

## Using Lauren's real export

The ingest layer auto-detects columns, so usually just point `--input` at the real CSV. If the headers
are unusual, pass `--filename-col` / `--path-col`. Then tune [`taxonomy/rules.yaml`](taxonomy/rules.yaml)
— add doc-type keywords and department/function folder mappings — and re-run. No code changes required.
