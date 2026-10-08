#!/bin/sh
# Run pytest with HOME isolated so no test can touch the live ~/.claude ledger.
set -eu
cd "$(dirname "$0")/../.."
iso="$(mktemp -d)"
cache="$(uv cache dir)"
HOME="$iso" CODEX_HOME="$iso/.codex" UV_CACHE_DIR="$cache" PYTHONDONTWRITEBYTECODE=1 \
  exec uv run --no-project --with pytest python -m pytest -p no:cacheprovider "$@"
