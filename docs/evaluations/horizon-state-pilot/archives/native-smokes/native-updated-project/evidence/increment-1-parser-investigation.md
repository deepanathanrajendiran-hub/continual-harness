# Increment 1 parser investigation

## Reproduction

Command:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

Observed results:

```text
test_empty_input_is_rejected (test_parser_example.ParserTests.test_empty_input_is_rejected) ... FAIL
test_valid_integer_is_preserved (test_parser_example.ParserTests.test_valid_integer_is_preserved) ... ok
test_zero_is_preserved (test_parser_example.ParserTests.test_zero_is_preserved) ... ok

AssertionError: ValueError not raised

Ran 3 tests in 0.000s
FAILED (failures=1)
```

This isolates the failure to empty input. The evaluator-owned acceptance tests already confirm that `"12"` parses as `12` and `"0"` parses as `0`.

## Cause

`parser_example.py` currently implements:

```python
def parse_number(value):
    return int(value or "0")
```

For `value == ""`, Python evaluates `value or "0"` to `"0"`. The function therefore calls `int("0")` and returns `0`, preventing the `ValueError` that `int("")` would normally raise. The same fallback is unnecessary for valid integer strings: both `int("12")` and `int("0")` already produce the required values.

## Minimal next fix

Replace the function body with `return int(value)`. This removes only the empty-string fallback, restores Python's native `ValueError` for empty input, and preserves valid integer parsing including zero. Do not modify `tests/test_parser_example.py`.
