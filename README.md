Gemini Flight Recorder is a local replay and regression tool for Gemini app failures. It turns raw Gemini traces into a readable timeline, detects common agent failure modes, replays the run under a changed prompt/config, and converts the failure into a regression test.

# Gemini Flight Recorder

> Gemini Flight Recorder turns a failed Gemini app run into a readable timeline, a replay, and a regression test.

## What is Gemini Flight Recorder?

Gemini Flight Recorder is a small Python CLI for developers building tool-using Gemini apps and AI Studio prototypes. It starts with a concrete failed run, normalizes the trace, labels high-signal failure modes, renders a local HTML timeline, replays the case in offline mock mode, and writes a JSONL regression case.

It is intentionally narrow: failed Gemini app run in, replayable regression artifact out.

## Why this exists

Gemini and AI Studio make it fast to prototype agents that call tools, retrieve data, and produce final answers. When a run fails, the raw log usually has the ingredients needed to debug it, but the developer still has to answer practical questions:

- What happened in order?
- Which tool result mattered?
- Did the final answer contradict the tool result?
- Can this failure become a repeatable test?

Gemini Flight Recorder bridges that gap locally. It complements logs by turning bad runs into replayable tests.

## 60-second demo

```bash
flightrec demo
```

The demo runs fully offline. It imports a failing refund-agent trace, generates a timeline, detects that the agent claimed a refund succeeded even though the refund tool timed out, replays the case with a tighter prompt in mock mode, and promotes the failure into a regression JSONL file.

Expected shape:

```text
Gemini Flight Recorder

Imported: examples/failing-refund-agent/trace.json
Status: FAILURE_DETECTED
Failure labels:
  - false_completion
  - tool_error_ignored
  - data_overreach
  - destructive_without_approval

Timeline:
  reports/failing-refund-agent/timeline.html
  reports/failing-refund-agent/timeline.md

Replay:
  original: claimed refund completed
  replay: refused to claim completion after tool error

Regression test written:
  evals/refund_failure_regression.jsonl
```

## Install

```bash
git clone https://github.com/raj200501/gemini-flight-recorder.git
cd gemini-flight-recorder
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Usage

```bash
flightrec import examples/failing-refund-agent/trace.json --out runs/refund
flightrec report runs/refund --html
flightrec detect runs/refund
flightrec replay runs/refund --mode mock --prompt examples/failing-refund-agent/prompt_tighter.md
flightrec promote runs/refund --out evals/refund_regression.jsonl
flightrec doctor
```

The CLI accepts a simple public JSON trace format:

```json
{
  "run_id": "refund-001",
  "source": "gemini-api",
  "model": "gemini-2.5-flash",
  "task": "Refund customer C123 for ticket T456",
  "messages": [{"role": "user", "content": "..."}],
  "events": [
    {"type": "model_call", "input": "...", "output": "..."},
    {"type": "tool_call", "tool_name": "refund_customer", "args": {"customer_id": "C123"}},
    {"type": "tool_result", "tool_name": "refund_customer", "error": "Refund API timeout"},
    {"type": "final_answer", "content": "The refund has been completed."}
  ]
}
```

## Example timeline

`flightrec report` writes:

- `timeline.json`
- `timeline.md`
- `timeline.html`
- `detections.json`

The HTML report is the primary product artifact. It is self-contained, local, and designed to make the failure readable at a glance:

```text
Gemini Flight Recorder
Failure timeline for refund-001

Status: FAILURE_DETECTED
Top failures:
1. Final answer claimed refund completion after refund tool timed out.
2. Agent fetched all customers for a single-ticket refund.
3. Destructive refund tool executed without approval event.
```

Sample artifacts live in `reports/sample-timeline.html` and `reports/sample-timeline.md`.

## Failure detectors

Gemini Flight Recorder ships with eight deterministic detectors:

| Code | Label | What it catches |
| --- | --- | --- |
| FR001 | `false_completion` | Final answer claims completion without successful tool confirmation. |
| FR002 | `tool_error_ignored` | Tool result failed, but the final answer omits failure, uncertainty, or next steps. |
| FR003 | `data_overreach` | Broad data access for a narrow task, such as `get_all_*`, `include_all: true`, `limit >= 1000`, or `SELECT *`. |
| FR004 | `destructive_without_approval` | Risky tool call without prior confirmation, approval, dry run, preview, or human review. |
| FR005 | `unsupported_evidence_claim` | Final answer claims grounding or verification without evidence/source events. |
| FR006 | `prompt_injection_followed` | Conservative heuristic for external instruction override text that appears to influence the final answer. |
| FR007 | `repeated_failed_tool_loop` | Same tool called three or more times with errors and unchanged arguments. |
| FR008 | `missing_traceability` | Tool-using trace lacks run ids, request ids, timestamps, or event ids. |

## Replay modes

### Mock mode

Mock mode is required and works offline:

```bash
flightrec replay runs/refund --mode mock --prompt examples/failing-refund-agent/prompt_tighter.md
```

For the refund demo, mock replay produces the corrected final answer:

```text
The refund could not be confirmed because the refund tool returned a timeout. I did not complete the refund.
```

It also records before/after status, detector changes, original final answer, replay final answer, and the changed prompt path in `runs/<name>/replay.json`.

### Gemini mode

Gemini mode is optional. It requires `GEMINI_API_KEY` and the optional `google-genai` package. The demo and tests do not require a real Gemini API key.

## Regression test format

`flightrec promote` writes JSONL cases shaped for future evals:

```json
{
  "case_id": "refund-tool-timeout-false-completion",
  "task": "Refund customer C123 for ticket T456",
  "original_trace": "runs/refund/trace.json",
  "expected_failures": ["false_completion", "tool_error_ignored"],
  "must_not_claim": ["refund completed", "successfully refunded"],
  "required_behavior": "The assistant must say the refund could not be confirmed if the refund tool errors.",
  "suggested_prompt": "...",
  "source_run_id": "refund-001"
}
```

## How this fits with AI Studio / Gemini logs

The first supported input is a small public JSON trace format that resembles common Gemini API and AI Studio app flows: user message, model call, tool call, tool result, final answer. It does not depend on private AI Studio exports or internal Google APIs.

Use it next to your existing logs. Export or adapt the bad run into the public trace shape, run `flightrec`, inspect the timeline, replay the case, and promote it into regression coverage.

## What it does not do

- It is not an official Google or Gemini product.
- It does not replace AI Studio logs.
- It is not a hosted observability dashboard.
- It is not a generic LangSmith, Langfuse, Braintrust, or AgentOps replacement.
- It does not require a Gemini API key for the demo.
- It does not send traces to a remote service.

## Design principles

- Failure-first: start from a concrete bad run.
- Replayable: every finding should become a reproducible case.
- Gemini-native: model/tool/final-answer flows should match Gemini app patterns.
- Offline demo: no credentials needed to understand the product.
- Local-first: no hosted dashboard.
- Regression-oriented: a failure is only useful if it becomes a future test.

## Roadmap

- Add import adapters for more real-world Gemini API log shapes.
- Add stricter matching between tasks and relevant tool results.
- Add config files for detector tuning.
- Add richer replay traces for multi-tool agents.
- Add eval runners that consume the generated JSONL directly.

## Disclaimer

This project is an independent local developer tool. It is not affiliated with, endorsed by, or sponsored by Google. It is designed to complement Gemini and AI Studio logs by helping developers turn failed local traces into replayable regression tests.

