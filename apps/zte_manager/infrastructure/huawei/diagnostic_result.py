from __future__ import annotations

import ast
import re


DIAGNOSTIC_SPLIT = "[@#@]"


_RETURN_FUNCTION = re.compile(
    r"^function(?:\s+[A-Za-z_$][\w$]*)?\s*\(\s*\)\s*\{\s*"
    r"return\s+(?P<expression>.*?)\s*;\s*\}\s*;?$",
    re.S,
)


def _decode_string_expression_node(node: ast.AST) -> str:
    """Decode only string constants joined with ``+``.

    Huawei EG8041 WebUIs return diagnostic polling frames as JavaScript-style
    string expressions such as ``"part1" + "part2" + "\\x5b...Complete"``.
    Python's AST can parse that subset without executing it. Any name, call,
    attribute, interpolation or operator other than string ``+`` is rejected.
    """

    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return (
            _decode_string_expression_node(node.left)
            + _decode_string_expression_node(node.right)
        )
    raise ValueError("unsupported Huawei diagnostic string expression")


def _diagnostic_string_expression(source: str) -> str:
    """Return the inert string expression contained in a Huawei poll frame.

    EG8041X6-10 physically returns both bare concatenated strings and an
    anonymous JavaScript function whose only statement is ``return <strings>``.
    We unwrap only that exact no-argument function grammar. The resulting
    expression is still parsed by the restrictive AST decoder below, so router
    JavaScript is never executed.
    """

    text = source.strip()
    wrapper = _RETURN_FUNCTION.fullmatch(text)
    if wrapper is not None:
        return wrapper.group("expression").strip()
    return text[:-1].rstrip() if text.endswith(";") else text


def decode_huawei_diagnostic_result(source: object) -> tuple[str, str]:
    """Decode a Huawei Get*Result.asp frame without evaluating router code.

    Supported inputs:
    - already-decoded plain text containing ``[@#@]``;
    - one quoted Python/JavaScript-compatible string literal;
    - a concatenation of quoted string literals using ``+``;
    - the same expression wrapped by ``function() { return ...; }``, as
      physically observed on EG8041X6-10 ping responses.

    Unknown syntax is preserved as text so callers keep the previous safe
    fallback behavior; executable expressions are never evaluated.
    """

    text = str(source or "").lstrip("\ufeff").strip()
    if not text:
        return "", ""

    expression = _diagnostic_string_expression(text)
    decoded: str | None = None

    if expression[:1] in {"'", '"'}:
        try:
            parsed = ast.parse(expression, mode="eval")
            decoded = _decode_string_expression_node(parsed.body)
        except (SyntaxError, ValueError, TypeError):
            # Preserve compatibility with the historical single-literal path.
            try:
                literal = ast.literal_eval(expression)
            except (SyntaxError, ValueError, TypeError):
                literal = None
            if isinstance(literal, str):
                decoded = literal

    if decoded is not None:
        text = decoded

    if DIAGNOSTIC_SPLIT not in text:
        return text.strip(), ""

    output, state = text.split(DIAGNOSTIC_SPLIT, 1)
    return output.strip(), state.strip()
