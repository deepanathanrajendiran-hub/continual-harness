# Increment 1: empty-input parser investigation

## Scope inspected

- Parser source: `/Users/deeps/Documents/NEW STUFF/fun /.superpowers/worktrees/horizon-state/.superpowers/sdd/2026-09-19-horizon-state-mode/native-baseline-project/parser_example.py`
- Evaluator-owned test: `/Users/deeps/Documents/NEW STUFF/fun /.superpowers/worktrees/horizon-state/.superpowers/sdd/2026-09-19-horizon-state-mode/native-baseline-project/tests/test_parser_example.py`
- Relevant symbol: `parser_example.parse_number`

No parser source or test files were changed.

## Current behavior

`parse_number("")` returns integer `0`. The evaluator expects the empty string to be rejected with `ValueError` (`ParserTests.test_empty_input_is_rejected`). Valid integer strings still behave as intended: `parse_number("0") == 0` and `parse_number("12") == 12`. A nonnumeric string such as `"abc"` already raises the normal `ValueError` from `int()`.

Focused verification command:

```text
python3 -B -m unittest discover -s tests -v
```

Observed result: 3 tests ran; 2 passed and `test_empty_input_is_rejected` failed with `AssertionError: ValueError not raised`.

## Cause

The complete implementation is currently:

```python
def parse_number(value):
    return int(value or "0")
```

Python evaluates the empty string as false, so `value or "0"` substitutes the literal string `"0"`. `int("0")` then returns `0`; the original empty input never reaches `int()`, which would otherwise reject it. This fallback also collapses distinct inputs into the same result and is unnecessary for preserving a genuine zero string because `"0"` is truthy.

## Proposed minimal fix

Remove the fallback and pass the supplied value directly to `int`:

```python
def parse_number(value):
    return int(value)
```

This is the smallest change that satisfies the existing contract: `int("")` raises `ValueError`, while `int("0")` and `int("12")` continue to return `0` and `12`. No test change is required.
