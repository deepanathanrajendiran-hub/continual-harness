#!/bin/bash
# Round 2 passes when /app/b.txt holds exactly "B" and round 1's /app/a.txt is still there.
mkdir -p /logs/verifier
if [ "$(cat /app/b.txt 2>/dev/null)" = "B" ] && [ "$(cat /app/a.txt 2>/dev/null)" = "A" ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
