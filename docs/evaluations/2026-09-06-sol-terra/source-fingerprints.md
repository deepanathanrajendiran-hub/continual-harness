# Source fingerprints

Before and after the trials, these SHA-256 values matched. Only evaluation reports
and evidence were added to the repository during this turn.

- `.agents/skills/horizon/SKILL.md`: `7fcacce4183baf14679e5d45324babc9535ba2017a4f249503f5310b91165b51`
- `.agents/skills/refine/SKILL.md`: `b0a6b683fc817ca4ef258776c1b25a830b8908d3f181994ab4b6bb86f17fc97a`
- `.claude/skills/horizon/SKILL.md`: `0926c33f5b9b4c8c4d9e7286e509af5364e7ccae4de1f543a6239ea56645fef7`
- `.claude/skills/refine/SKILL.md`: `e4a6941d0302417fbaa67c9ee065f0909b4c0545d83ef6bb2d643c88eac21d8e`
- `harness/cli.py`: `ed1c302d9541996039b1e5d1f31533c397c9cd965dcaa46cd86b7064f8c581a3`
- `harness/filelock.py`: `7cc6adb675f9aa501d3b639a2d2f30cfd33d287076db1dc4b3f12a4a33cc57df`
- `harness/gate.py`: `e52cdf8fd5dc3151e40e674f5572e67ee80787f1f98b99b50e386968926c6e81`
- `harness/goal.py`: `552515dbbf5e6eafc661b21fc7b448683c0963ac9e66d89c3112ffe0e3834a95`
- `harness/paths.py`: `5020e8820e977a811dfaa7d79e3cbca0aa7a0136262b9ff8aa7f050b2dd2d79a`
- `harness/refine_log.py`: `09ac9fad92f517c28690c2f6692ddecdf2952715edb9871951083d8e1984f1aa`
- `harness/tree_hash.py`: `361e187d0756fc727615b1c55da55e3c274b126848f82363d6a676061b7849b3`

# Parent state checks

```json
{
  "checks": "passed",
  "goals": [
    {
      "case": "sol-horizon",
      "slug": "produce-a-brief-actionable-web-app-release-runbook-with-prer",
      "status": "complete",
      "turns": 2,
      "max_turns": 3
    },
    {
      "case": "resume-project",
      "slug": "create-foundation-txt-and-delivery-txt-each-containing-exact",
      "status": "complete",
      "turns": 2,
      "max_turns": 3
    },
    {
      "case": "budget-project",
      "slug": "produce-ready-txt-containing-the-accepted-marker",
      "status": "active",
      "turns": 1,
      "max_turns": 1
    }
  ],
  "refinement_reverted": true,
  "confirmed_defect": "three literal backslash-n sequences in a one-line note"
}
```
