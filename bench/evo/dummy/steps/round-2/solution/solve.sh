#!/bin/bash
set -euo pipefail
cd /app
bash /opt/evo-check/probe.sh record round-2
printf 'B\n' > b.txt
