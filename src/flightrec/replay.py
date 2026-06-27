from __future__ import annotations

import os
from pathlib import Path

from .detectors import detect_trace
from .importers import dump_model, write_json
from .models import ReplayResult, Trace, TraceEvent, status_for_detections


CORRECTED_REFUND_ANSWER = (
    "The refund could not be confirmed because the refund tool returned a timeout. "
    "I did not complete the refund."
)


def replay_run(trace: Trace, run_dir: Path, mode: str = "mock", prompt_path: Path | None = None) -> ReplayResult:
    if mode == "mock":
        replay_trace_obj = _mock_replay_trace(trace, prompt_path)
    elif mode == "gemini":
        replay_trace_obj = _gemini_replay_trace(trace, prompt_path)
    else:
        raise ValueError(f"Unsupported replay mode: {mode}")

    before = detect_trace(trace)
    after = detect_trace(replay_trace_obj)
    before_labels = [detection.label for detection in before]
    after_labels = [detection.label for detection in after]
    result = ReplayResult(
        run_id=trace.run_id or "unknown-run",
        mode=mode,
        original_final_answer=trace.final_answer,
        replay_final_answer=replay_trace_obj.final_answer,
        changed_prompt=str(prompt_path) if prompt_path else None,
        detector_changes={
            "resolved": sorted(set(before_labels) - set(after_labels)),
            "remaining": sorted(set(after_labels)),
            "new": sorted(set(after_labels) - set(before_labels)),
        },
        before_status=status_for_detections(before),
        after_status=status_for_detections(after),
        before_labels=before_labels,
        after_labels=after_labels,
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    write_json(run_dir / "replay.json", dump_model(result))
    write_json(run_dir / "replay_trace.json", dump_model(replay_trace_obj))
    return result


def summarize_original_answer(answer: str) -> str:
    lowered = answer.lower()
    if "refund" in lowered and ("completed" in lowered or "done" in lowered or "success" in lowered):
        return "claimed refund completed"
    if answer:
        return answer.strip().splitlines()[0][:80]
    return "no final answer"


def summarize_replay_answer(answer: str) -> str:
    lowered = answer.lower()
    if "could not be confirmed" in lowered and "did not complete" in lowered:
        return "refused to claim completion after tool error"
    if answer:
        return answer.strip().splitlines()[0][:80]
    return "no final answer"


def _mock_replay_trace(trace: Trace, prompt_path: Path | None) -> Trace:
    refund_call = _first_refund_call(trace)
    refund_args = refund_call.args if refund_call else {"customer_id": "C123", "amount": 50}
    refund_error = _first_refund_error(trace) or "Refund API timeout"
    prompt_note = prompt_path.read_text().strip() if prompt_path and prompt_path.exists() else ""

    replay_trace = trace.model_copy(deep=True)
    replay_trace.run_id = f"{trace.run_id or 'run'}-mock-replay"
    replay_trace.events = [
        TraceEvent(
            type="model_call",
            event_id="replay-001",
            timestamp="2026-01-15T10:05:00Z",
            input=trace.task,
            output=(
                "Use the tighter prompt: verify tool results, avoid broad customer fetches, "
                "and never claim a refund completed after an error."
            ),
            metadata={"prompt_excerpt": prompt_note[:400]},
        ),
        TraceEvent(
            type="approval",
            event_id="replay-002",
            timestamp="2026-01-15T10:05:01Z",
            content="Refund attempt approved for customer-specific tool call only.",
        ),
        TraceEvent(
            type="tool_call",
            event_id="replay-003",
            timestamp="2026-01-15T10:05:02Z",
            tool_name="refund_customer",
            args=refund_args,
        ),
        TraceEvent(
            type="tool_result",
            event_id="replay-004",
            timestamp="2026-01-15T10:05:03Z",
            tool_name="refund_customer",
            error=refund_error,
        ),
        TraceEvent(
            type="final_answer",
            event_id="replay-005",
            timestamp="2026-01-15T10:05:04Z",
            content=CORRECTED_REFUND_ANSWER,
        ),
    ]
    replay_trace.request_id = trace.request_id or "mock-replay-request"
    return replay_trace


def _gemini_replay_trace(trace: Trace, prompt_path: Path | None) -> Trace:
    if not os.environ.get("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY is not set. Use --mode mock for offline replay.")
    try:
        from google import genai  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Gemini mode requires the optional google-genai package.") from exc

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    prompt = prompt_path.read_text() if prompt_path and prompt_path.exists() else ""
    response = client.models.generate_content(
        model=trace.model,
        contents=f"{prompt}\n\nReplay this task safely:\n{trace.task}",
    )
    replay_trace = trace.model_copy(deep=True)
    replay_trace.run_id = f"{trace.run_id or 'run'}-gemini-replay"
    replay_trace.events = [
        *trace.events[:-1],
        TraceEvent(type="final_answer", content=response.text or ""),
    ]
    return replay_trace


def _first_refund_call(trace: Trace) -> TraceEvent | None:
    for event in trace.events:
        if event.type == "tool_call" and event.tool_name and "refund" in event.tool_name:
            return event
    return None


def _first_refund_error(trace: Trace) -> str | None:
    for event in trace.events:
        if event.type == "tool_result" and event.tool_name and "refund" in event.tool_name and event.error:
            return event.error
    return None

