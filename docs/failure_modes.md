# Failure Modes And Detector Limits

This document lists known ways Gemini Flight Recorder can be wrong. The current scope is still useful because the tool is meant to turn representative failed local traces into regression fixtures, not to score broad model quality.

## Known False Positives

- Completion wording in a denial can look like success. Example: "This cannot be completed successfully" contains completion words. The detector includes negation checks, but unusual phrasing can still trigger.
- Data overreach is heuristic. A `get_all_*` tool can be appropriate for some admin tasks, but it is flagged when the task looks narrow.
- Destructive approval checks only look for prior approval-like events. An application might enforce approval outside the trace.
- Evidence claims depend on event naming. A trace with real evidence under an unknown custom field might be flagged as unsupported.
- Prompt injection detection is conservative but text based. It can flag a trace where the final answer quotes an injected phrase only to explain why it was rejected.

## Known False Negatives

- A model can imply success without words such as "completed", "done", or "successfully".
- A relevant tool can fail while an unrelated tool succeeds; the current heuristic does not fully match tool relevance to task intent.
- Prompt injection can be followed without repeating an obvious phrase from the external content.
- Evidence can be low quality even when source events exist. The tool checks trace presence, not source quality.
- Repeated retries with slightly changed arguments may still be a loop, but FR007 only flags unchanged arguments.

## Mitigation Ideas

- Add app-specific detector config for relevant tools and acceptable approval events.
- Keep regression JSONL cases next to app evals so app owners can add expected behavior.
- Preserve source, retrieval, and citation event names in adapters.
- Add golden fixtures whenever a false positive or false negative is found.
- Use strict mode only where the detector set is appropriate for that app's release gate.

## Why This Scope Is Useful

The first question after a failed agent run is often not "what is the universal model accuracy?" It is "what happened here, and can we keep this from coming back?" These heuristics make that loop fast for common Gemini-style traces while keeping the limits visible.
