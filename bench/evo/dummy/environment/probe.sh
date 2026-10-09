#!/bin/bash
# Behaviour-check probe for the EvoCode first look (bench/evo/harborcheck.py). No EvoCode content.
#   probe.sh plant         record round-1, plant what round 2 must or must not see, record round-1-planted
#   probe.sh record LABEL  record what this process can see into /logs/artifacts/probe/LABEL/
# EVO_CHECK_ROOT and EVO_CHECK_DECOY exist only so the unit test can run this outside a container.
set -u
R="${EVO_CHECK_ROOT:-}"
H="${HOME:-/root}"

record() {
  out="$R/logs/artifacts/probe/$1"
  mkdir -p "$out"
  pwd > "$out/pwd.txt"
  id -un > "$out/user.txt" 2>&1
  printf '%s\n' "$H" > "$out/home.txt"
  ls -A "$R/tmp" > "$out/tmp.txt" 2>&1
  ls -A . > "$out/project.txt" 2>&1
  ls -A "$R/tests" > "$out/tests.txt" 2>&1
  ls -A "$R/logs/verifier" > "$out/verifier.txt" 2>&1
  (cd "$H" 2>/dev/null && find .claude 2>/dev/null | LC_ALL=C sort) > "$out/dot-claude.txt"
  find .claude/harness -type f 2>/dev/null | LC_ALL=C sort > "$out/ledger.txt"
  for d in "$R"/proc/[0-9]*; do
    [ -r "$d/cmdline" ] || continue
    args="$(tr '\0' ' ' < "$d/cmdline" 2>/dev/null)"
    [ -n "$args" ] || continue
    ppid="$(awk '/^PPid:/ {print $2}' "$d/status" 2>/dev/null)"
    printf '%s %s %s\n' "${d##*/}" "${ppid:-?}" "${args% }"
  done > "$out/procs.txt"
}

plant() {
  printf 'sentinel\n' > "$R/tmp/evo-check-sentinel"
  mkdir -p .claude/harness/goals .claude/harness/gates/check-gate "$H/.claude/projects/-app/memory"
  printf '{"slug": "check-goal", "status": "active"}\n' > .claude/harness/goals/check-goal.json
  printf 'check gate request\n' > .claude/harness/gates/check-gate/request.md
  printf 'memory\n' > "$H/.claude/projects/-app/memory/check.md"
  if [ "${EVO_CHECK_DECOY:-1}" = 1 ]; then
    # A stray "claude": its command line is "claude 86399"; the collect hook must kill it.
    setsid nohup bash -c 'exec -a claude sleep 86399' > /dev/null 2>&1 < /dev/null &
    sleep 1
  fi
}

case "${1:-}" in
  plant) record round-1; plant; record round-1-planted ;;
  record) record "${2:?usage: probe.sh record LABEL}" ;;
  *) echo "usage: probe.sh plant | probe.sh record LABEL" >&2; exit 2 ;;
esac
exit 0
