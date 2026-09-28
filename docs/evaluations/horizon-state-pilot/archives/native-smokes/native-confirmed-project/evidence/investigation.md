# Empty-input parser investigation

`parse_number` currently returns `int(value or "0")`. For an empty string, the boolean fallback replaces `""` with `"0"`, so `parse_number("")` returns `0` instead of allowing `int("")` to raise `ValueError`.

Focused verification with `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v` ran three acceptance tests: `test_empty_input_is_rejected` failed because no `ValueError` was raised, while the valid-integer and zero-preservation tests passed. A direct read-only probe produced `[('', 0), ('0', 0), ('42', 42), ('-7', -7)]`.

The minimal next change is to remove the falsy fallback and pass `value` directly to `int`, which lets Python reject empty input while preserving valid integers, including zero.

No parser source or test source was changed during this investigation. Before recording this note, SHA-256 was `d170165014bb83537c7b470400c733c756b8971b3c743fbcabf3a6dff9865217` for `parser_example.py` and `e280cf50c2b5b21c99b9aa6e42f67dc140862afa64dbd3a8c84cda94a6ebab86` for `tests/test_parser_example.py`.
