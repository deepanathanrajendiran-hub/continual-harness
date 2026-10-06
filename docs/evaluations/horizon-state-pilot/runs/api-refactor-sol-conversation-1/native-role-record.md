# Native role record

- Coordinator: `/root/pilot_api_refactor_sol_conversation_1`; model `gpt-5.6-sol`; reasoning `high`; owns Horizon lifecycle, evidence capture, gate, reviewer dispatch, and report.
- Editing worker: `/root/pilot_api_refactor_sol_conversation_1/editing_worker`; model `gpt-5.6-sol`; reasoning `high`; fresh context via `fork_turns: none`; owns one source-edit increment only; no Horizon lifecycle authority.
- Independent reviewer: `/root/pilot_api_refactor_sol_conversation_1/independent_reviewer`; model `gpt-5.6-sol`; reasoning `high`; fresh context via `fork_turns: none`; source/evidence inspection only; no editing or lifecycle authority.

Coordinator-written tool accounts are saved separately from native role terminal transcripts.
