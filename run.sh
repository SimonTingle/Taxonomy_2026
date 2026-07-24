#!/usr/bin/env bash
#
# Bootstrap + run the document taxonomy pipeline end to end.
#
#   ./run.sh                      # classify Book1.csv (or the sample) + prep the UI data
#   ./run.sh --input export.csv   # classify a specific CSV
#   ./run.sh --serve              # also start the React UI dev server
#   ./run.sh --input x.csv --filename-col col_0 --path-col col_1
#
set -euo pipefail
cd "$(dirname "$0")"

# ---- config / args --------------------------------------------------------
INPUT=""
SERVE=0
EXTRA_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --input|-i) INPUT="$2"; shift 2 ;;
    --serve)    SERVE=1; shift ;;
    *)          EXTRA_ARGS+=("$1"); shift ;;
  esac
done

# Default input: prefer the real export if present, else the bundled sample.
if [[ -z "$INPUT" ]]; then
  if [[ -f "Book1.csv" ]]; then INPUT="Book1.csv"; else INPUT="data/sample_export.csv"; fi
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR=".venv"
OUT_DIR="out"

echo "==> Input CSV : $INPUT"

# ---- python env -----------------------------------------------------------
if [[ ! -d "$VENV_DIR" ]]; then
  echo "==> Creating virtualenv ($VENV_DIR)"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
echo "==> Installing Python dependencies"
pip install -q --upgrade pip >/dev/null
pip install -q -r requirements.txt

# ---- classify -------------------------------------------------------------
echo "==> Running classifier"
python -m taxonomy.cli --input "$INPUT" --out "$OUT_DIR" ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}

# ---- stage data for the UI ------------------------------------------------
echo "==> Copying outputs into web/public/"
mkdir -p web/public
cp "$OUT_DIR/classified.csv" "$OUT_DIR/summary.json" web/public/

# ---- optional: start the UI ----------------------------------------------
if [[ "$SERVE" -eq 1 ]]; then
  echo "==> Starting the review UI (http://localhost:5173)"
  cd web
  [[ -d node_modules ]] || npm install
  npm run dev
else
  echo ""
  echo "Done. To view the review UI:"
  echo "    cd web && npm install && npm run dev"
  echo "Or re-run with --serve to launch it automatically."
fi
