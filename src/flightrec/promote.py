from __future__ import annotations

import json
import re
from pathlib import Path

from .detectors import detect_trace
from .models import RegressionCase, Trace


def promote_run(trace: Trace, run_dir: Path, out_path: Path) -> RegressionCase:
    detections = detect_trace(trace)
    labels = [detection.label for detection in detections]
    replay_prompt = _read_replay_prompt(run_dir)
    case = RegressionCase(
        case_id=_case_id(trace, labels),
        task=trace.task,
        original_trace=str(run_dir / "trace.json"),
        expected_failures=labels,
        must_not_claim=_must_not_claim(trace),
        required_behavior=_required_behavior(trace),
        suggested_prompt=replay_prompt,
        source_run_id=trace.run_id,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(case.model_dump(mode="json", exclude_none=True), sort_keys=False) + "\n")
    return case


def _case_id(trace: Trace, labels: list[str]) -> str:
    task = trace.task.lower()
    if "refund" in task and "false_completion" in labels:
        return "refund-tool-timeout-false-completion"
    words = re.findall(r"[a-z0-9]+", trace.run_id or trace.task.lower())
    base = "-".join(words[:6]) or "gemini-regression"
    return base


def _must_not_claim(trace: Trace) -> list[str]:
    task = trace.task.lower()
    if "refund" in task:
        return ["refund completed", "successfully refunded", "refund has been completed"]
    return ["completed successfully", "done", "successfully completed"]


def _required_behavior(trace: Trace) -> str:
    task = trace.task.lower()
    if "refund" in task:
        return "The assistant must say the refund could not be confirmed if the refund tool errors."
    return "The assistant must not claim task completion when required tool calls fail."


def _read_replay_prompt(run_dir: Path) -> str | None:
    replay_path = run_dir / "replay.json"
    if not replay_path.exists():
        return None
    data = json.loads(replay_path.read_text())
    prompt_path = data.get("changed_prompt")
    if not prompt_path:
        return None
    path = Path(prompt_path)
    if path.exists():
        return path.read_text()
    return prompt_path

