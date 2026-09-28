# Protocol-freeze preflight verification

Command run independently in each prepared fixture directory:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

| Fixture | Seed exit | Reference-repair exit | Observed reason |
| --- | ---: | ---: | --- |
| `module-bug` | 1 | 0 | Seed totals 240 rather than 270 at 10%; repair passes. |
| `api-refactor` | 1 | 0 | Seed lacks `normalize_name`; repair passes. |
| `test-repair` | 1 | 0 | Seed accepts booleans/negative counts; repair passes. |
| `checkpoint-handoff` | 1 | 0 | Seed lacks `delivery`; repair passes. |
| `interrupted-edit` | 1 | 0 | Seed renders `a,b,c` instead of `"a,b",c`; repair passes. |
| `stale-fact` | 0 | 0 | Initial old contract passes; the separately retained parser-only transition fails before the consumer repair, then the repair passes. |

The full prepared seed outputs, including tracebacks and fixture byte hashes,
are preserved byte-for-byte in [prepared-seed-output.md](prepared-seed-output.md).
Reference repair output and the parser-only stale transition are in
`../../reference-only/`.  This preflight proves fixture readiness only; it is
not a measured native role, coordination, handoff, interruption, or scoring
result.
