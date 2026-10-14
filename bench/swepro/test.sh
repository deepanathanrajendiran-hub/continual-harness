#!/bin/sh
# Run pytest with HOME isolated (no test may touch the live ~/.claude) and Harbor 0.24.0 importable.
set -eu
cd "$(dirname "$0")/../.."
iso="$(mktemp -d)"
cache="$(uv cache dir)"
pythons="$(uv python dir)"
HOME="$iso" CODEX_HOME="$iso/.codex" UV_CACHE_DIR="$cache" UV_PYTHON_INSTALL_DIR="$pythons" PYTHONDONTWRITEBYTECODE=1 \
  exec uv run --no-project --python 3.12 --with pytest --with harbor==0.24.0 python -m pytest -p no:cacheprovider "$@"
