# `results.jsonl` record contract

Append one object after independent scoring, never before.  Every field below
is required.  `null` means the raw evidence did not establish the value;
numeric zero means the evidence established zero.  `packet_bytes` is an array
of observed packet byte counts and is never a token/cost estimate.

```json
{"fixture":"module-bug","model":"gpt-5.6-sol","mode":"state","repeat":1,
 "gate_passed":false,"reported_complete":false,"false_completion":false,
 "regressions":0,"repeated_work_events":[],"state_omissions":[],
 "stale_fact_events":[],"handoff_recovered":null,"worker_launches":0,
 "reserved_attempts":0,"checkpoints":0,"format_repairs":0,
 "elapsed_seconds":0,"packet_bytes":[],"total_tokens":null,"cost":null,
 "usage_source":"unavailable","evidence_dir":"runs/module-bug-sol-state-1",
 "protocol_deviations":[]}
```

The example is a schema illustration only and must not be copied as a result.
`false_completion` is true only when an agent reported completion while
evaluator acceptance or a required review failed.  `repeated_work_events`
contains actual duplicated edits/investigations with evidence references; a
stale-file reread alone is not one.  Record aborted launches, unavailable hosts,
and altered timing/role arrangements under `protocol_deviations`.  Leave
`total_tokens` and `cost` null unless host usage is consistently available for
coordinator, worker, and reviewer in both arms.
