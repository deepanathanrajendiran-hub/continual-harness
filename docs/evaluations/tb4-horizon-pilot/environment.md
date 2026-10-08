# Environment record

Written before the freeze. Every value here is part of the frozen protocol.

## Versions

- harbor: `0.24.0`
- claude (host): `2.1.293 (Claude Code)`
- python (host): `3.14.4`
- terminal-bench commit: `452bf305c6daa62fc59061d22133a7cbc7c1572e`
- repository commit: `24c138c4af11c2e81fd67bd575db785780ed759f`

## Docker

- server: `29.1.3`
- cpus and memory bytes: `8 12529250304`

## Horizon bundle

Commit `2f65f2a24d753b6875bd126fc989335baff82ed8`.

| File | SHA-256 |
| --- | --- |
| `horizon/SKILL.md` | `9cbd38f352d606360610f086b60cb2f51d6d14603e22f4f73e3e9a9fb620d691` |
| `horizon/references/commands.md` | `04817de80b3f667d73a05c82ba3ec6c79eb1c9f24e0d8c6ae6d41bfffec7fdee` |
| `horizon/scripts/filelock.py` | `7b134fd00d93c81c3d6e4093a42095f86786189f5ce29d3e9c30a377f1b208e6` |
| `horizon/scripts/gate.py` | `9ac4961c2ddb733dc2e192c527608084a400bcd35187fad34fc10a41476b6ffc` |
| `horizon/scripts/goal.py` | `4ef46c065f2c3ba232806452d0973de221467b1ef102b24f6d468580f34bb519` |
| `horizon/scripts/harness.py` | `41f9a00f5ca409b3b165b354e54a9a4f52edfd4ecbca127a757f8e4b9652ffbb` |
| `horizon/scripts/paths.py` | `5020e8820e977a811dfaa7d79e3cbca0aa7a0136262b9ff8aa7f050b2dd2d79a` |
| `horizon/scripts/refine_log.py` | `09ac9fad92f517c28690c2f6692ddecdf2952715edb9871951083d8e1984f1aa` |
| `horizon/scripts/steps.py` | `e1bf7b5e517efe0d6aba722789c9c39b875a3243646ec0691be5bb1fdb2df761` |
| `horizon/scripts/task_state.py` | `1ade30d217978a8ac1abe1677ffc7d83ca73d42000d65c3cf61f303dcadac9ad` |
| `horizon/scripts/tree_hash.py` | `361e187d0756fc727615b1c55da55e3c274b126848f82363d6a676061b7849b3` |

## Tasks, images, and copies

| Order | Task | Workdir | Agent image | Verifier image | Copy digest |
| --- | --- | --- | --- | --- | --- |
| 0 | layout-config-recreation | `/app` | `sha256:681e2d45fb91a8ef26ddf92217e58d4a261e7b4352ba4aeaff6b24ed7bbb6057` | `sha256:26f84d868a96c0ee45fd348bd46e3fb72aa904a418352244108a91b3471301bf` | `02660f09b15265496b1785069181cd74cfb976e5d4fec6b0544c5111f76f957d` |
| 1 | cargo-flight-dispatch | `/app` | `sha256:c25adcbc587abe325fc84649f2d6b708b47d7c00a0fbad4ca47eee8302e8636f` | `sha256:dd1965b411d311e4529237677d9815038e834147e67a425ddd1bfbcce8e6843b` | `a7a562e7afd8375ced1c494f044a4c5ca5e55c7f0618e58cc41e8028f0549914` |
| 2 | sglang-qwen-burst | `/app/sglang` | `sha256:188a8398d7a9162779353c53238af40e738010e4b6d753acb3bdff650e8f95a9` | `sha256:fdb13991f29115b799ff4f6980c8e009b6472caa342ce481bc7d053b9ea10188` | `b23aa4d7b8106b2d54035c118198cf0325b96d1572d69850e58b885a7937fdd0` |
| 3 | session-window-debug | `/app` | `sha256:11972179f438aed1b49a441298eac2e1191418f32a673b6ef2a4a5bc36ff8cd1` | `sha256:cab7ed9a70abb45dfef2879ef01ae3d77d46797650a97544e2a65f0f25c966f3` | `1c018bcb546bac98a4cb3b4207f537abf0a0897ea762a9685a06111f722549f0` |
| 4 | roy-polymorph-cn | `/app` | `sha256:b348b0cb42e33e9b37f38c4532c98be47e77623e00919d4c428f4e6b4f1ce8e0` | `sha256:ae0901e4153dcb3c48bb7b8515143b7275de10d27eafa97a6a53c41a768293c4` | `2aa02b6bd4188b9568b53731421403be4ddb46e3861df95c8f64d434e0711a12` |
| 5 | formal-crypto | `/app` | `sha256:b38c68c7cfb72f8f39449089a53596116a3589b703b6e1229b61836179827fb6` | `sha256:0011d52f055509009e77c30887acb32490fd57d327ca483cebc3147f513f64aa` | `2060e365bd797b522df1f1ee69bd8872527723bda5d5bb90afdad34a314ea248` |
| 6 | satb-audio-transcription | `/app` | `sha256:ad653593893914ce835333d415521debcfeeb75ea5391bb0322fb4e1eeb8ccb6` | `sha256:106299c7c9d21297b2854fa71daa749fa8ee2b32fd4b7759f90cebe1bd3c6491` | `43540d6bd8da2dd052132c5f9c618fd31d36900d8d68acb09537bda00a6c8501` |
| 7 | production-planning | `/app` | `sha256:47ebeb69bffc288611062bc88faad32de817e2cb0906f6c195e86a68ad6d28dd` | `sha256:99de29de99e76b264f8323172d85026de172a688b8ab2cee6c11b32139e1b519` | `e98d35e669c46ba1bb0c732983bba144e49913cafd1d5ae88dd34148b2a0e752` |
| 8 | embedding-drift-monitor | `/app` | `sha256:5d84da9138932035f158fdf21a253e2b1a4950e669cf4f90e662b0773aab7aac` | `sha256:46a038455aedc82092261bf74964e77c986dcd7f1405c69214d4c7c385ab7c26` | `007c7f270dd655946e64f8a264a2ce5c8bf7591417b639f93dd1bab6cac3ac85` |
| 9 | mvcc-lsm-compaction | `/app` | `sha256:9cc21b6e51811a0aceb5dfb6729ae76353ac4024eaf27767a899037d51e2a8a2` | `sha256:0d646038a6f078f470bed5e635aca30eece7f8160c55de79f5adcd55a664e442` | `fde7d3685972ca430443dc62b7605175237708e3cb8be219d2f398e3aae4c3f9` |
| 10 | protein-autointerp-disulfide | `/app` | `sha256:3a13e45969e33ed03ae8ba82b5c26952ba6ca40353a7f38495be7a0ad592fe74` | `sha256:0639b4d62a8da627b0d6d6a48ceb359d51bfd11a803854f631208f250d3b7ebf` | `e8aed9a971675c44b56a9b7b86c5894677ece36067bc029e70a8f1dbd235e6ff` |

## Prompt files

| File | SHA-256 |
| --- | --- |
| `control.md` | `ce27bb41ae86a77710bbc43f6a7aa0bce684195109b8e85893cab6750b8873f7` |
| `horizon.md` | `1b1a7ec7fb378c5ecae812b8ab8be3d4d21c0b1f8188ee08057d11e575e07fd3` |
| `judge.md` | `f11fde652e21dc09c827c1561cad6e0b9a0be7cf421eecbba00a49543b319f07` |
