# Frozen implementation and skill snapshot

The protocol was frozen from Git commit
`2f65f2a24d753b6875bd126fc989335baff82ed8`.  A measured row must record the
actual checkout identity and compare these files before dispatch.  A changed
source/skill snapshot is a protocol deviation, not a reason to silently update
one arm.

| Path | SHA-256 |
| --- | --- |
| `harness/cli.py` | `41f9a00f5ca409b3b165b354e54a9a4f52edfd4ecbca127a757f8e4b9652ffbb` |
| `harness/goal.py` | `4ef46c065f2c3ba232806452d0973de221467b1ef102b24f6d468580f34bb519` |
| `harness/gate.py` | `9ac4961c2ddb733dc2e192c527608084a400bcd35187fad34fc10a41476b6ffc` |
| `harness/filelock.py` | `7b134fd00d93c81c3d6e4093a42095f86786189f5ce29d3e9c30a377f1b208e6` |
| `harness/task_state.py` | `1ade30d217978a8ac1abe1677ffc7d83ca73d42000d65c3cf61f303dcadac9ad` |
| `harness/steps.py` | `e1bf7b5e517efe0d6aba722789c9c39b875a3243646ec0691be5bb1fdb2df761` |
| `.agents/skills/horizon/SKILL.md` | `7c1dc1edf666a9c4644da8f4e54a87eccb1f6b6bc7cc276e7590c44536af7dbf` |
| `.claude/skills/horizon/SKILL.md` | `9cbd38f352d606360610f086b60cb2f51d6d14603e22f4f73e3e9a9fb620d691` |
| `docs/harness-cli.md` | `04817de80b3f667d73a05c82ba3ec6c79eb1c9f24e0d8c6ae6d41bfffec7fdee` |
| `README.md` | `707a41361453aff1182e0dce2ae4830ec35e70bb4c993e563e19ad55ceb194b8` |

`manifest.csv` has SHA-256
`b4bab2621e85e1983f58ed4cc60f42030d18c7ed70fd459ec3902f1658d4f3b4`
and 72 data rows.  The trial runner must make a trial-local project marker
before using the CLI and must not repoint a global `HOME` or `CODEX_HOME`.
