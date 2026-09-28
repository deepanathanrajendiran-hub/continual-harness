# Pilot reference repairs

These separate copies demonstrate that the frozen acceptance cases pass known repairs. They are evaluator artifacts, not measured model results and must not be supplied to measured workers. All Python changes used the AST editor; rename references were inspected first.

## module-bug

Acceptance exit 0; evaluator-owned test bytes unchanged.

```text
test_total_and_boundaries (test_acceptance.AcceptanceTests.test_total_and_boundaries) ... ok

----------------------------------------------------------------------
Ran 1 test in 0.000s

OK
```

### pricing.py

SHA-256: `d90b510771d75fa0fbc4b7b42115c97812bbb6e3d494d56e9b495925f38a2a12`

```python
def discounted(amount, percent):
    return amount * (100 - percent) // 100

```

## api-refactor

Acceptance exit 0; evaluator-owned test bytes unchanged.

```text
test_names_and_callers (test_acceptance.AcceptanceTests.test_names_and_callers) ... ok

----------------------------------------------------------------------
Ran 1 test in 0.000s

OK
```

### greet.py

SHA-256: `b0eb603b4f53661a32f0477eebb52d25e81becb6b0ac55f438f6fb8fe8604878`

```python
from names import normalize_name

def greet(value):
    return "Hello " + normalize_name(value)

```

### names.py

SHA-256: `09b84dc3cf84531060aa4439ff6af23d304aab67e6406e9b2e1de0040f9a2b5e`

```python
def normalize_name(value):
    return value.strip().casefold()

normalize = normalize_name

```

### tags.py

SHA-256: `b2e22fd1cdcde0196180b088548ef65728b661f5f9c77ed31e06fa415afea8b7`

```python
from names import normalize_name

def tag(value):
    return "#" + normalize_name(value)

```

## test-repair

Acceptance exit 0; evaluator-owned test bytes unchanged.

```text
test_invalid_counts (test_acceptance.AcceptanceTests.test_invalid_counts) ... ok
test_valid_counts (test_acceptance.AcceptanceTests.test_valid_counts) ... ok

----------------------------------------------------------------------
Ran 2 tests in 0.000s

OK
```

### counts.py

SHA-256: `53b9e266c34c758cba62207f0087eb91a81f83e82c120b88587a20e2f6b05935`

```python
def parse_count(value):
    if isinstance(value, bool):
        raise ValueError("booleans are not counts")
    count = int(value)
    if count < 0:
        raise ValueError("counts must be nonnegative")
    return count

```

## checkpoint-handoff

Acceptance exit 0; evaluator-owned test bytes unchanged.

```text
test_delivery (test_acceptance.AcceptanceTests.test_delivery) ... ok

----------------------------------------------------------------------
Ran 1 test in 0.000s

OK
```

### delivery.py

SHA-256: `022e0f18f3e26929421466fc34a1a9985222ba06c4ad684c4138d922de06e91f`

```python
from foundation import slug

def slugs(values):
    return [slug(value) for value in values]

```

## interrupted-edit

Acceptance exit 0; evaluator-owned test bytes unchanged.

```text
test_csv_and_empty (test_acceptance.AcceptanceTests.test_csv_and_empty) ... ok

----------------------------------------------------------------------
Ran 1 test in 0.000s

OK
```

### render.py

SHA-256: `fd4f728f8a21bc11fdf21b3600bc9db3f09d9ef5ce60ec55b6ffc4ef1c407f10`

```python
import csv
from io import StringIO
def render_row(values):
    output = StringIO()
    csv.writer(output, lineterminator="").writerow(values)
    return output.getvalue()

```

## stale-fact

Acceptance exit 0; evaluator-owned test bytes unchanged.

```text
test_current_parser_contract (test_acceptance.AcceptanceTests.test_current_parser_contract) ... ok

----------------------------------------------------------------------
Ran 1 test in 0.000s

OK
```

### consumer.py

SHA-256: `2ce815e99c3c6c6583262a178f4ede7b0f8f11333bf2d2941eee99c91186d0e4`

```python
from parser import parse_number

def parse(value):
    return parse_number(value)

```

### parser.py

SHA-256: `47a9b605388ad834f09374c004ca06a0149392ee3f314a5a4c6b69ded69e8420`

```python
def parse_number(value):
    if value == "":
        raise ValueError("empty input is invalid")
    return int(value)

```

## Stale dependency transition

Before changing the consumer, replacing only parser.py with the exact planned new dependency made the unchanged acceptance fail (exit1). Raw output:

```text
test_current_parser_contract (test_acceptance.AcceptanceTests.test_current_parser_contract) ... FAIL

======================================================================
FAIL: test_current_parser_contract (test_acceptance.AcceptanceTests.test_current_parser_contract)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/deeps/Documents/NEW STUFF/fun /.superpowers/worktrees/horizon-state/.superpowers/sdd/2026-09-19-horizon-state-mode/pilot-reference-repairs/stale-fact/tests/test_acceptance.py", line 9, in test_current_parser_contract
    expected = parser.parse_number("")
  File "/Users/deeps/Documents/NEW STUFF/fun /.superpowers/worktrees/horizon-state/.superpowers/sdd/2026-09-19-horizon-state-mode/pilot-reference-repairs/stale-fact/parser.py", line 3, in parse_number
    raise ValueError("empty input is invalid")
ValueError: empty input is invalid

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/Users/deeps/Documents/NEW STUFF/fun /.superpowers/worktrees/horizon-state/.superpowers/sdd/2026-09-19-horizon-state-mode/pilot-reference-repairs/stale-fact/tests/test_acceptance.py", line 11, in test_current_parser_contract
    with self.assertRaises(ValueError):
         ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^
AssertionError: ValueError not raised

----------------------------------------------------------------------
Ran 1 test in 0.000s

FAILED (failures=1)
```

The later reference consumer repair passed against that new parser. Source fixture seeds remain unchanged. Foundation bytes were preserved in the reference copy; per-run mtime preservation remains a measured-trial requirement, not established by this reference check.
