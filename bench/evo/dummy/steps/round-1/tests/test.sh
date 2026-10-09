#!/bin/bash
# Round 1 passes when /app/a.txt holds exactly "A".
# harborcheck's verifier-timeout variant adds /tests/sleep_sec so this outlives a short verifier timeout.
if [ -f /tests/sleep_sec ]; then sleep "$(cat /tests/sleep_sec)"; fi
mkdir -p /logs/verifier
ls -A /tests > /logs/verifier/round1-verifier-marker.txt 2>&1
if [ "$(cat /app/a.txt 2>/dev/null)" = "A" ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
