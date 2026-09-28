# Increment 2 worker account

## AST edit

The AST editor capability was discovered in the active tool registry as `mcp__ast_editor__*`.

1. Called `mcp__ast_editor__list_symbols` for `native-baseline-project/parser_example.py` before editing. Result: `function parse_number (line 1)`.
2. Called `mcp__ast_editor__replace_function_body` with target `parse_number` and body `return int(value)`. Result: `Successfully replaced body of 'parse_number'`.

Changed file: `native-baseline-project/parser_example.py`. Its implementation is now:

```python
def parse_number(value):
    return int(value)
```

The evaluator-owned file `native-baseline-project/tests/test_parser_example.py` was not edited.

## Verification

Command:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

Output summary: all 3 tests passed (`test_empty_input_is_rejected`, `test_valid_integer_is_preserved`, and `test_zero_is_preserved`); `Ran 3 tests in 0.000s`; `OK`.

No `__pycache__` directory was created under the project.
