# Gemini Flight Recorder Spec

This document defines the public/local artifacts used by Gemini Flight Recorder. The schemas are intentionally small so a developer can adapt Gemini API logs, AI Studio-like local exports, or test harness traces without private APIs.

## Input Assumptions

Flight Recorder expects a JSON trace with:

- one run-level task;
- optional request and run identifiers;
- ordered events;
- model/tool/final-answer events that resemble Gemini app traces;
- enough tool result detail to tell whether a tool returned an error.

The native format is `generic`. The `gemini-json` and `ai-studio-loglike` formats are adapters for simple local JSON shapes. They are not private AI Studio export parsers.

## Trace Schema

Machine-readable schema: `schemas/trace.schema.json`.

Stable fields:

```json
{
  "schema_version": "flightrec.trace.v1",
  "run_id": "refund-001",
  "request_id": "req-refund-001",
  "source": "gemini-api",
  "model": "gemini-2.5-flash",
  "task": "Refund customer C123 for ticket T456",
  "messages": [{"role": "user", "content": "Please refund customer C123."}],
  "events": [
    {"type": "tool_call", "tool_name": "refund_customer", "args": {"customer_id": "C123"}},
    {"type": "tool_result", "tool_name": "refund_customer", "error": "Refund API timeout"},
    {"type": "final_answer", "content": "The refund has been completed."}
  ]
}
```

## Finding Schema

Machine-readable schema: `schemas/finding.schema.json`.

Each finding is a deterministic heuristic label:

```json
{
  "schema_version": "flightrec.finding.v1",
  "code": "FR001",
  "label": "false_completion",
  "severity": "high",
  "title": "Final answer claimed completion without successful tool confirmation",
  "detail": "Final answer used completion language while refund_customer returned Refund API timeout.",
  "event_indices": [2, 1],
  "recommendation": "Only claim completion after the relevant tool result confirms success."
}
```

## Report Schema

Machine-readable schema: `schemas/report.schema.json`.

Reports summarize a normalized trace, detector output, replay output if present, and regression metadata if present. Stable fields include:

- `schema_version`
- `run_id`
- `source`
- `model`
- `task`
- `status`
- `readiness_score`
- `severity_counts`
- `detections`
- `events`
- optional `replay`
- optional `regression`

## Regression JSONL Schema

Machine-readable schema: `schemas/regression.schema.json`.

Each JSONL line is one future eval case:

```json
{
  "schema_version": "flightrec.regression.v1",
  "case_id": "refund-tool-timeout-false-completion",
  "task": "Refund customer C123 for ticket T456",
  "original_trace": "runs/refund/trace.json",
  "expected_failures": ["false_completion", "tool_error_ignored"],
  "must_not_claim": ["refund completed", "successfully refunded"],
  "required_behavior": "The assistant must say the refund could not be confirmed if the refund tool errors.",
  "source_run_id": "refund-001"
}
```

## Status, Severity, And Readiness

Severity is assigned by detector rule:

- `high`: likely user-visible task contradiction, ignored tool failure, destructive action issue, prompt injection following, or retry loop.
- `medium`: missing evidence for grounding claims or missing traceability.
- `low`: reserved for future advisory findings.

Status is derived from findings:

- `PASS`: no findings.
- `REVIEW_RECOMMENDED`: findings exist, but none are high severity.
- `FAILURE_DETECTED`: at least one high severity finding exists.

Readiness score is a local report signal, not an accuracy metric:

- start at `100`;
- subtract `35` per high finding;
- subtract `15` per medium finding;
- subtract `5` per low finding;
- clamp to `0..100`.

## Versioning Strategy

Schemas use stable string versions such as `flightrec.trace.v1`. Compatible additive fields may be added within `v1`. Breaking changes should create a new schema version and keep import adapters for older artifacts where practical.

## Compatibility Notes

The Pydantic models allow extra fields. This lets local adapters preserve useful log metadata while keeping detector behavior focused on known fields.

## Limitations

Flight Recorder does not execute tools, inspect private logs, or prove correctness. It flags common trace-level patterns that are useful for development regression coverage. Production-grade use would need app-specific tool semantics, stronger evidence provenance, configurable detector thresholds, and integration with the app's own eval runner.
