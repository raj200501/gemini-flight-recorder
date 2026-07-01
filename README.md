# Gemini Flight Recorder

Local replay and regression tooling for Gemini app failures.

Flight Recorder turns a failed Gemini-style trace into a readable timeline, detector labels, a mock replay, and a regression JSONL case.

```bash
flightrec demo
```

```text
Run: failing-refund-agent
Status: FAILURE_DETECTED
Failure labels: false_completion, tool_error_ignored, data_overreach, destructive_without_approval
Timeline: reports/failing-refund-agent/timeline.html
Regression: evals/refund_failure_regression.jsonl
```

## Proof Of Concept

| Signal | Checked-in evidence |
| --- | --- |
| Detectors | 8 deterministic detector labels for trace-level Gemini app failure modes. |
| Fixtures | 14 trace fixtures, including 8 adversarial traces for near misses and unusual layouts. |
| Report artifacts | `timeline.html`, `timeline.md`, `timeline.json`, `detections.json`, and regression JSONL output. |
| Test surface | 38 collected pytest cases, plus CI on Python 3.10, 3.11, and 3.12. |
| Offline replay | `flightrec demo` imports traces, detects failures, performs mock replay, and promotes regression cases without a Gemini API key. |

## What It Detects

Flight Recorder starts from a concrete failed run. It normalizes the trace, labels deterministic failure patterns, renders a local report, replays the case in offline mock mode, and promotes the run into regression coverage.

| Code | Label | What it catches |
| --- | --- | --- |
| FR001 | `false_completion` | Final answer claims completion without successful tool confirmation. |
| FR002 | `tool_error_ignored` | Tool result failed, but the final answer omits failure or uncertainty. |
| FR003 | `data_overreach` | Broad data access for a narrow task. |
| FR004 | `destructive_without_approval` | Risky tool call without a prior approval-like event. |
| FR005 | `unsupported_evidence_claim` | Grounding, citation, or verification language without evidence events. |
| FR006 | `prompt_injection_followed` | External instruction text appears to influence the final answer. |
| FR007 | `repeated_failed_tool_loop` | Same tool called repeatedly with errors and unchanged arguments. |
| FR008 | `missing_traceability` | Tool-using trace lacks identifiers or timestamps needed to correlate the run. |

## Why This Exists

Gemini and AI Studio make it fast to build tool-using apps. When a run fails, the raw trace usually has enough information to debug it, but it is easy to lose the regression value of the failure.

Flight Recorder keeps the failure local, readable, and repeatable: trace in, timeline and labels out, replay and JSONL case ready for future tests.

## Why This Is Not Just Tracing

Tracing tells you what happened. Flight Recorder turns a bad Gemini run into a replayable regression case.

The useful step is after inspection: the tool labels the failure, produces a deterministic mock replay, and writes the JSONL artifact you can keep as future eval coverage.

## Part Of A Small Gemini Builder Trust Loop

- **ShipCheck** asks: "Should I share or deploy this Gemini app yet?"
- **Flight Recorder** asks: "Why did this Gemini run fail, and can I turn it into a regression test?"
- **Interactions Doctor** asks: "Is this Gemini app harness wired for state, tools, tests, traces, and iteration?"

The tools are separate local utilities with related questions. This is not a company, platform, or claim of official Google affiliation.

## Credibility And Limitations

Flight Recorder checks public/local JSON traces. It does not execute real tools, inspect private AI Studio exports, rate source quality, prove answer correctness, or require a Gemini API key for the demo.

False positives can come from unusual negation, app-level approval checks that are not represented in the trace, custom evidence fields, or broad tools that are appropriate for a specific app. False negatives can come from subtle implied completion, prompt injection that does not repeat a clear phrase, low-quality evidence events, or retry loops that change arguments slightly.

Mock replay is deterministic and detector-aware. Gemini replay is optional and only runs when `GEMINI_API_KEY` and the optional SDK are available.

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
flightrec import examples/failing-refund-agent/trace.json --format generic --out runs/refund
flightrec report runs/refund --html
flightrec detect runs/refund
flightrec replay runs/refund --mode mock --prompt examples/failing-refund-agent/prompt_tighter.md
flightrec promote runs/refund --out evals/refund_regression.jsonl
flightrec doctor
flightrec version
```

The CLI accepts a small public JSON trace format and includes adapters for `generic`, `gemini-json`, and `ai-studio-loglike` local shapes. It does not depend on private AI Studio formats.

Normal commands exit `0` when the tool ran successfully, even when findings exist. Use `--strict` where a non-`PASS` status should fail CI.

## Development

```bash
make verify
make demo
make reports
make clean
```

Optional Gemini replay requires `GEMINI_API_KEY` and the optional `google-genai` dependency:

```bash
python -m pip install -e ".[dev,gemini]"
GEMINI_API_KEY=... make live-smoke
```

## Docs

- [Trace and report schema](docs/spec.md)
- [Failure modes](docs/failure_modes.md)
- [Evaluation notes](docs/evaluation.md)
- [Suite positioning](docs/suite.md)
- Machine-readable schemas in [schemas/](schemas/)

## Disclaimer

Gemini Flight Recorder is an independent local developer tool. It is not affiliated with, endorsed by, or sponsored by Google. It does not guarantee security, correctness, factuality, compliance, policy alignment, or production readiness.
