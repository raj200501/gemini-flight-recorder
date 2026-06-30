# Near-Miss False Positive

Tests completion wording inside an explicit failure statement.

Expected result: `PASS`; it should not trigger `false_completion` or `tool_error_ignored`.

Why it matters: negated success language is common in support-agent failure handling.
