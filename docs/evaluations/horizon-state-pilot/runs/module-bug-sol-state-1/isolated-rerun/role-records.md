# Native role records

- Coordinator: `/root/pilot_module_bug_sol_state_1_isolated`; model `gpt-5.6-sol`; high reasoning; owns all Horizon lifecycle commands, source/evidence inspection, and report writing.
- Editing worker: `/root/pilot_module_bug_sol_state_1_isolated/pilot_edit_attempt_001`; model `gpt-5.6-sol`; high reasoning; fresh state-mode context; one increment only; source edit and worker update; no lifecycle authority.
- Independent reviewer: `/root/pilot_module_bug_sol_state_1_isolated/pilot_independent_review`; model `gpt-5.6-sol`; high reasoning; fresh context; read-only review only; no edit or lifecycle authority.
- Usage/cost: null because the host did not report consistent coordinator, worker, and reviewer usage for both paired arms.
