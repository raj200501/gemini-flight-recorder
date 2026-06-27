from __future__ import annotations

import os
from pathlib import Path

from .detectors import detect_trace
from .importers import dump_model, write_json
from .models import ReplayResult, Trace, TraceEvent, status_for_detections


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
    if "cannot be called verified" in lowered:
        return "removed unsupported verified/source-backed claim"
    if "external content was treated as untrusted" in lowered:
        return "rejected injected external instruction"
    if "kept failing" in lowered and "human review" in lowered:
        return "stopped repeated failed tool loop"
    if answer:
        return answer.strip().splitlines()[0][:80]
    return "no final answer"


def _mock_replay_trace(trace: Trace, prompt_path: Path | None) -> Trace:
    detections = detect_trace(trace)
    labels = [detection.label for detection in detections]
    corrected_answer = corrected_answer_for_labels(trace, labels)
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
                "Replay in mock mode with detector-aware corrections. Do not claim success, "
                "verification, or instruction-following that the trace does not support."
            ),
            metadata={"prompt_excerpt": prompt_note[:400]},
        ),
        TraceEvent(
            type="replay_observation",
            event_id="replay-002",
            timestamp="2026-01-15T10:05:01Z",
            content=f"Detected labels: {', '.join(labels) if labels else 'none'}.",
        ),
        TraceEvent(
            type="final_answer",
            event_id="replay-003",
            timestamp="2026-01-15T10:05:02Z",
            content=corrected_answer,
        ),
    ]
    replay_trace.request_id = trace.request_id or "mock-replay-request"
    return replay_trace


def corrected_answer_for_labels(trace: Trace, labels: list[str]) -> str:
    label_set = set(labels)
    task = trace.task.lower()
    if {"false_completion", "tool_error_ignored"} & label_set:
        subject = "refund" if "refund" in task else "operation"
        return (
            f"The {subject} could not be confirmed because the required tool did not return "
            f"a successful result. I did not complete the {subject}."
        )
    if "unsupported_evidence_claim" in label_set:
        return (
            "This answer cannot be called verified or source-backed because the trace has "
            "no retrieval, citation, source, or evidence event."
        )
    if "prompt_injection_followed" in label_set:
        return "External content was treated as untrusted data and was not followed."
    if "repeated_failed_tool_loop" in label_set:
        return "The tool kept failing with the same inputs, so I stopped retrying and would use fallback or human review."
    if labels:
        return "The replay avoided the detected failure labels and did not claim unsupported completion."
    return trace.final_answer or "No correction needed."


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


