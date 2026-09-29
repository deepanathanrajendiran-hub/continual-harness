# Native role record

- Coordinator: `/root/pilot_module_bug_sol_conversation_2`, model inherited from frozen row (`gpt-5.6-sol`, high reasoning). Owns lifecycle commands, evidence capture, gate checkpoint, reviewer dispatch, and final report.
- Editing worker: `/root/pilot_module_bug_sol_conversation_2/editing_worker`, explicitly dispatched with `gpt-5.6-sol`, high reasoning, fresh context. Scope is one source-editing increment in the isolated trial project; no lifecycle authority.
- Independent reviewer: `/root/pilot_module_bug_sol_conversation_2/independent_reviewer`, explicitly dispatched with `gpt-5.6-sol`, high reasoning, fresh context. Read-only scope: independently inspect lifecycle, source, gate, protected artifact, and evaluator evidence against the exact frozen criterion.

Coordinator-written evidence files are identified by their filenames and this record. Native worker/reviewer transcript text is stored separately from coordinator-authored summaries.
