#!/usr/bin/env bash
#
# Bootstrap, classify, and launch the review UI in one step.
# Shorthand for: ./run.sh --serve
#
#   ./run-serve.sh
#   ./run-serve.sh --input export.csv
#
set -euo pipefail
cd "$(dirname "$0")"
exec ./run.sh --serve "$@"
