# Pilot seed preparation

Controller preparation during Task 8. These ignored disposable Python files were authored exclusively with AST editor list_symbols/add_import/add_top_level. No measured pilot run has started. Task 10 must verify reference repairs, preserve these exact seeds and acceptance hashes, freeze its manifest/protocol in Git, then run the comparisons.

The foundation handoff seed intentionally has no delivery.py. Its acceptance therefore fails to import delivery; the first increment is reserved for foundation inspection before the new coordinator implements delivery. Stale-fact initially passes under the old parser contract; the declared parser change must produce the later failure without changing tests.

## module-bug

### checkout.py

SHA-256: `82de323e0cddff692abb6cea7fc7ff3ed6794a769bb5b48ec39edbf36fd103bb`

```python
from pricing import discounted

def total(amounts, percent):
    return sum(discounted(amount, percent) for amount in amounts)

```

### pricing.py

SHA-256: `a9d31ee865900e44f33eb6aab70ea7d9880bf2bc8c1e5cd796354b0587969500`

```python
def discounted(amount, percent):
    return amount * (100 - percent * 2) // 100

```

### tests/test_acceptance.py

SHA-256: `cb50420a69e7abef79d5b50043ef39e82bfbffb16edb1b58b0f4202d5693442d`

```python
import unittest
from checkout import total

class AcceptanceTests(unittest.TestCase):
    def test_total_and_boundaries(self):
        self.assertEqual(total([100, 200], 10), 270)
        self.assertEqual(total([], 10), 0)
        self.assertEqual(total([100, 200], 0), 300)

```

Acceptance command: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`. Exit 1.

```text
test_total_and_boundaries (test_acceptance.AcceptanceTests.test_total_and_boundaries) ... FAIL

======================================================================
FAIL: test_total_and_boundaries (test_acceptance.AcceptanceTests.test_total_and_boundaries)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/deeps/Documents/NEW STUFF/fun /.superpowers/worktrees/horizon-state/.superpowers/sdd/2026-09-19-horizon-state-mode/pilot-seeds/module-bug/tests/test_acceptance.py", line 6, in test_total_and_boundaries
    self.assertEqual(total([100, 200], 10), 270)
    ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: 240 != 270

----------------------------------------------------------------------
Ran 1 test in 0.000s

FAILED (failures=1)
```

## api-refactor

### greet.py

SHA-256: `f4e2bc6755318e5ecbb9b52e0c8174d5342512d171229b5a666acac02d97f6fb`

```python
from names import normalize

def greet(value):
    return "Hello " + normalize(value)

```

### names.py

SHA-256: `c9eb9fffca5197eb3193ac1d0ccea0136d347104e3652bfc1817abcbd54038a2`

```python
def normalize(value):
    return value.strip().casefold()

```

### tags.py

SHA-256: `45627c624d598d3172896d7b3276b6643407f2a36a5360b49efdee530673987a`

```python
from names import normalize

def tag(value):
    return "#" + normalize(value)

```

### tests/test_acceptance.py

SHA-256: `cabb3c9379120181bc94744b6915cd9add3bb489c5009cf8553d532928ce9297`

```python
import unittest
from names import normalize, normalize_name
from greet import greet
from tags import tag

class AcceptanceTests(unittest.TestCase):
    def test_names_and_callers(self):
        self.assertEqual(normalize_name(" ALICE "), "alice")
        self.assertEqual(normalize(" ALICE "), normalize_name(" ALICE "))
        self.assertEqual(greet(" ALICE "), "Hello alice")
        self.assertEqual(tag(" ALICE "), "#alice")

```

Acceptance command: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`. Exit 1.

```text
test_acceptance (unittest.loader._FailedTest.test_acceptance) ... ERROR

======================================================================
ERROR: test_acceptance (unittest.loader._FailedTest.test_acceptance)
----------------------------------------------------------------------
ImportError: Failed to import test module: test_acceptance
Traceback (most recent call last):
  File "/opt/homebrew/Cellar/python@3.14/3.14.4/Frameworks/Python.framework/Versions/3.14/lib/python3.14/unittest/loader.py", line 426, in _find_test_path
    module = self._get_module_from_name(name)
  File "/opt/homebrew/Cellar/python@3.14/3.14.4/Frameworks/Python.framework/Versions/3.14/lib/python3.14/unittest/loader.py", line 367, in _get_module_from_name
    __import__(name)
    ~~~~~~~~~~^^^^^^
  File "/Users/deeps/Documents/NEW STUFF/fun /.superpowers/worktrees/horizon-state/.superpowers/sdd/2026-09-19-horizon-state-mode/pilot-seeds/api-refactor/tests/test_acceptance.py", line 2, in <module>
    from names import normalize, normalize_name
ImportError: cannot import name 'normalize_name' from 'names' (/Users/deeps/Documents/NEW STUFF/fun /.superpowers/worktrees/horizon-state/.superpowers/sdd/2026-09-19-horizon-state-mode/pilot-seeds/api-refactor/names.py)


----------------------------------------------------------------------
Ran 1 test in 0.000s

FAILED (errors=1)
```

## test-repair

### counts.py

SHA-256: `14446c2474baa1449a318f2e4f741ea65ebfae8ecd7abafa8bf52fced999956e`

```python
def parse_count(value):
    return int(value)

```

### tests/test_acceptance.py

SHA-256: `0dd145fbaa42b2393bf9f3d12c0017401b464005afd88a9f020daf84be2e35d5`

```python
import unittest
from counts import parse_count

class AcceptanceTests(unittest.TestCase):
    def test_valid_counts(self):
        self.assertEqual(parse_count("12"), 12)
        self.assertEqual(parse_count("0"), 0)

    def test_invalid_counts(self):
        for value in (True, False, -1, "-1", "bad"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_count(value)

```

Acceptance command: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`. Exit 1.

```text
test_invalid_counts (test_acceptance.AcceptanceTests.test_invalid_counts) ... 
  test_invalid_counts (test_acceptance.AcceptanceTests.test_invalid_counts) (value=True) ... FAIL
  test_invalid_counts (test_acceptance.AcceptanceTests.test_invalid_counts) (value=False) ... FAIL
  test_invalid_counts (test_acceptance.AcceptanceTests.test_invalid_counts) (value=-1) ... FAIL
  test_invalid_counts (test_acceptance.AcceptanceTests.test_invalid_counts) (value='-1') ... FAIL
test_valid_counts (test_acceptance.AcceptanceTests.test_valid_counts) ... ok

======================================================================
FAIL: test_invalid_counts (test_acceptance.AcceptanceTests.test_invalid_counts) (value=True)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/deeps/Documents/NEW STUFF/fun /.superpowers/worktrees/horizon-state/.superpowers/sdd/2026-09-19-horizon-state-mode/pilot-seeds/test-repair/tests/test_acceptance.py", line 12, in test_invalid_counts
    with self.assertRaises(ValueError):
         ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^
AssertionError: ValueError not raised

======================================================================
FAIL: test_invalid_counts (test_acceptance.AcceptanceTests.test_invalid_counts) (value=False)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/deeps/Documents/NEW STUFF/fun /.superpowers/worktrees/horizon-state/.superpowers/sdd/2026-09-19-horizon-state-mode/pilot-seeds/test-repair/tests/test_acceptance.py", line 12, in test_invalid_counts
    with self.assertRaises(ValueError):
         ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^
AssertionError: ValueError not raised

======================================================================
FAIL: test_invalid_counts (test_acceptance.AcceptanceTests.test_invalid_counts) (value=-1)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/deeps/Documents/NEW STUFF/fun /.superpowers/worktrees/horizon-state/.superpowers/sdd/2026-09-19-horizon-state-mode/pilot-seeds/test-repair/tests/test_acceptance.py", line 12, in test_invalid_counts
    with self.assertRaises(ValueError):
         ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^
AssertionError: ValueError not raised

======================================================================
FAIL: test_invalid_counts (test_acceptance.AcceptanceTests.test_invalid_counts) (value='-1')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/deeps/Documents/NEW STUFF/fun /.superpowers/worktrees/horizon-state/.superpowers/sdd/2026-09-19-horizon-state-mode/pilot-seeds/test-repair/tests/test_acceptance.py", line 12, in test_invalid_counts
    with self.assertRaises(ValueError):
         ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^
AssertionError: ValueError not raised

----------------------------------------------------------------------
Ran 2 tests in 0.001s

FAILED (failures=4)
```

## checkpoint-handoff

### foundation.py

SHA-256: `8748b469317b07cb9de810c6504c4f24806c7738db4977f07a7d29d33486ad72`

```python
def slug(value):
    return "-".join(value.strip().lower().split())

```

### tests/test_acceptance.py

SHA-256: `949adcf37b09bd6ffeb49d55e5fc9a198d10ecc2c485a45fc68f31b2945b9f54`

```python
import unittest
from delivery import slugs

class AcceptanceTests(unittest.TestCase):
    def test_delivery(self):
        self.assertEqual(slugs([" Hello World ", "Two"]), ["hello-world", "two"])
        self.assertEqual(slugs([]), [])

```

Acceptance command: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`. Exit 1.

```text
test_acceptance (unittest.loader._FailedTest.test_acceptance) ... ERROR

======================================================================
ERROR: test_acceptance (unittest.loader._FailedTest.test_acceptance)
----------------------------------------------------------------------
ImportError: Failed to import test module: test_acceptance
Traceback (most recent call last):
  File "/opt/homebrew/Cellar/python@3.14/3.14.4/Frameworks/Python.framework/Versions/3.14/lib/python3.14/unittest/loader.py", line 426, in _find_test_path
    module = self._get_module_from_name(name)
  File "/opt/homebrew/Cellar/python@3.14/3.14.4/Frameworks/Python.framework/Versions/3.14/lib/python3.14/unittest/loader.py", line 367, in _get_module_from_name
    __import__(name)
    ~~~~~~~~~~^^^^^^
  File "/Users/deeps/Documents/NEW STUFF/fun /.superpowers/worktrees/horizon-state/.superpowers/sdd/2026-09-19-horizon-state-mode/pilot-seeds/checkpoint-handoff/tests/test_acceptance.py", line 2, in <module>
    from delivery import slugs
ModuleNotFoundError: No module named 'delivery'


----------------------------------------------------------------------
Ran 1 test in 0.000s

FAILED (errors=1)
```

## interrupted-edit

### render.py

SHA-256: `acea953c965f307a93856b0cdaa0e114bd51bb7d1be75ef51bd8996a2c9efbb3`

```python
def render_row(values):
    return ",".join(values)

```

### tests/test_acceptance.py

SHA-256: `51741aad445173fc00caa9c95ccd3bde03a74227f8b67bd3976f1d589dca9a1f`

```python
import unittest
from render import render_row

class AcceptanceTests(unittest.TestCase):
    def test_csv_and_empty(self):
        self.assertEqual(render_row(["a,b", "c"]), '"a,b",c')
        self.assertEqual(render_row([]), "")

```

Acceptance command: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`. Exit 1.

```text
test_csv_and_empty (test_acceptance.AcceptanceTests.test_csv_and_empty) ... FAIL

======================================================================
FAIL: test_csv_and_empty (test_acceptance.AcceptanceTests.test_csv_and_empty)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/deeps/Documents/NEW STUFF/fun /.superpowers/worktrees/horizon-state/.superpowers/sdd/2026-09-19-horizon-state-mode/pilot-seeds/interrupted-edit/tests/test_acceptance.py", line 6, in test_csv_and_empty
    self.assertEqual(render_row(["a,b", "c"]), '"a,b",c')
    ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: 'a,b,c' != '"a,b",c'
- a,b,c
+ "a,b",c
? +   +


----------------------------------------------------------------------
Ran 1 test in 0.000s

FAILED (failures=1)
```

## stale-fact

### consumer.py

SHA-256: `264e0dcd27b0985d8b5564e35e251dba4632a666d3e12e46c669960fab55ba54`

```python
from parser import parse_number

def parse(value):
    return 0 if value == "" else parse_number(value)

```

### parser.py

SHA-256: `d170165014bb83537c7b470400c733c756b8971b3c743fbcabf3a6dff9865217`

```python
def parse_number(value):
    return int(value or "0")

```

### tests/test_acceptance.py

SHA-256: `76c8715d5ecef2c386a754f3ed64dfda9f6d8b335b6f3c33419f0709c9b3830c`

```python
import unittest
import parser
import consumer

class AcceptanceTests(unittest.TestCase):
    def test_current_parser_contract(self):
        self.assertEqual(consumer.parse("7"), parser.parse_number("7"))
        try:
            expected = parser.parse_number("")
        except ValueError:
            with self.assertRaises(ValueError):
                consumer.parse("")
        else:
            self.assertEqual(consumer.parse(""), expected)

```

Acceptance command: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`. Exit 0.

```text
test_current_parser_contract (test_acceptance.AcceptanceTests.test_current_parser_contract) ... ok

----------------------------------------------------------------------
Ran 1 test in 0.000s

OK
```
