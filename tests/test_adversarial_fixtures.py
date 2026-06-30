from pathlib import Path

from flightrec.detectors import detect_trace
from flightrec.importers import load_trace
from flightrec.models import status_for_detections


ROOT = Path(__file__).resolve().parents[1]


def labels_for(path: Path) -> list[str]:
    trace = load_trace(path)
    return [detection.label for detection in detect_trace(trace)]


def status_for(path: Path) -> str:
    trace = load_trace(path)
    return status_for_detections(detect_trace(trace))


def test_adversarial_expected_labels() -> None:
    cases = {
        "01-obvious-bad": {"false_completion", "tool_error_ignored", "destructive_without_approval"},
        "02-obvious-good": set(),
        "03-near-miss-false-positive": set(),
        "05-harmless-wording": set(),
        "06-risky-wording": {"unsupported_evidence_claim"},
        "07-structured-safe-pattern": set(),
    }

    for fixture, expected in cases.items():
        labels = set(labels_for(ROOT / "examples" / "adversarial" / fixture / "trace.json"))
        assert labels == expected, fixture


def test_near_miss_false_negative_boundary_is_documented() -> None:
    labels = set(labels_for(ROOT / "examples/adversarial/04-near-miss-false-negative/trace.json"))

    assert "tool_error_ignored" in labels
    assert "destructive_without_approval" in labels
    assert "false_completion" not in labels


def test_unusual_nested_layout_imports_cleanly() -> None:
    path = ROOT / "examples/adversarial/08-unusual-layout/nested/trace.json"

    assert labels_for(path) == []
    assert status_for(path) == "PASS"
