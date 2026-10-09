#!/bin/bash
set -euo pipefail
cd /app
bash /opt/evo-check/probe.sh plant
printf 'A\n' > a.txt
