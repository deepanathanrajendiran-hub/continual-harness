# Increment 2 parser fix

- Editor: AST editor `list_symbols` followed by `replace_function_body` on `parse_number`.
- Source change: `parser_example.py` now returns `int(value)`, so empty input raises `ValueError` while valid integers and zero remain accepted.
- Acceptance: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v` passed all 3 tests.
- Evaluator test preservation: `tests/test_parser_example.py` was not edited; SHA-256 remains `e280cf50c2b5b21c99b9aa6e42f67dc140862afa64dbd3a8c84cda94a6ebab86`.
