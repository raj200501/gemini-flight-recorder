from pathlib import Path

from flightrec.detectors import detect_trace
from flightrec.importers import load_trace


ROOT = Path(__file__).resolve().parents[1]


def labels_for(example: str) -> set[str]:
    trace = load_trace(ROOT / "examples" / example / "trace.json")
    return {detection.label for detection in detect_trace(trace)}


def test_unsupported_research_agent_triggers_fr005() -> None:
    assert "unsupported_evidence_claim" in labels_for("unsupported-research-agent")


def test_prompt_injection_agent_triggers_fr006() -> None:
    assert "prompt_injection_followed" in labels_for("prompt-injection-agent")


def test_repeated_tool_loop_triggers_fr007() -> None:
    assert "repeated_failed_tool_loop" in labels_for("repeated-tool-loop")


def test_safe_run_triggers_no_failures() -> None:
    assert labels_for("safe-run") == set()


def test_grounded_research_agent_triggers_no_unsupported_evidence() -> None:
    assert labels_for("grounded-research-agent") == set()
