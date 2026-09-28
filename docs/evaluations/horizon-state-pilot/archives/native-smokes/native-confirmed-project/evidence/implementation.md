# Parser implementation and verification

Changed `parse_number` from `return int(value or "0")` to `return int(value)`. This removes only the empty-input fallback: `int("")` raises `ValueError`, while valid integer strings, including `"0"`, retain Python's normal integer conversion.

Verification ran once after the edit with:

`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`

Result: exit code 0; all 3 tests passed (`test_empty_input_is_rejected`, `test_valid_integer_is_preserved`, and `test_zero_is_preserved`).

The evaluator-owned test file was preserved exactly. Its SHA-256 before and after the edit was `e280cf50c2b5b21c99b9aa6e42f67dc140862afa64dbd3a8c84cda94a6ebab86` for `tests/test_parser_example.py`.

The updated `parser_example.py` SHA-256 is `b1bf7a081d3bdcc25979f4bc1a57be5d53a4709fc111593f332ccf432ccedfad`.
