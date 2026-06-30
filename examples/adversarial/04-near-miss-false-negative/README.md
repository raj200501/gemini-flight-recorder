# Near-Miss False Negative

Tests implied completion without the exact FR001 completion words.

Expected result: `FAILURE_DETECTED` from `tool_error_ignored` and `destructive_without_approval`, but not necessarily `false_completion`.

Why it matters: it documents a current heuristic boundary while still checking the failure is not silent.
