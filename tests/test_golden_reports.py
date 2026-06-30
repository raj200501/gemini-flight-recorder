import json
from pathlib import Path

from flightrec.detectors import detect_trace
from flightrec.importers import dump_model, import_trace, load_trace
from flightrec.models import Detection, RegressionCase, status_for_detections
from flightrec.promote import promote_run
from flightrec.reports import generate_reports, readiness_score, severity_counts


ROOT = Path(__file__).resolve().parents[1]
GOLDEN_DIR = ROOT / "tests" / "golden"


def test_golden_detection_summaries() -> None:
    for golden_path in sorted(GOLDEN_DIR.glob("*.json")):
        expected = json.loads(golden_path.read_text())
        trace = load_trace(ROOT / "examples" / expected["example"] / "trace.json")
        detections = detect_trace(trace)
        labels = [detection.label for detection in detections]

        assert status_for_detections(detections) == expected["status"], golden_path.name
        assert readiness_score(detections) == expected["readiness_score"], golden_path.name
        assert severity_counts(detections) == expected["severity_counts"], golden_path.name
        assert labels == expected["labels"], golden_path.name
        for absent_label in expected["absent_labels"]:
            assert absent_label not in labels, golden_path.name


def test_generated_report_json_has_stable_fields(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "refund"
    report_root = tmp_path / "reports"
    trace = import_trace(ROOT / "examples/failing-refund-agent/trace.json", run_dir)

    paths = generate_reports(run_dir, trace, report_root)
    report = json.loads(paths["timeline_json"].read_text())

    assert report["schema_version"] == "flightrec.report.v1"
    assert report["status"] == "FAILURE_DETECTED"
    assert report["readiness_score"] == 0
    assert report["severity_counts"] == {"high": 4, "medium": 0, "low": 0}
    assert [finding["label"] for finding in report["detections"]] == [
        "false_completion",
        "tool_error_ignored",
        "data_overreach",
        "destructive_without_approval",
    ]
    assert "events" in report


def test_detection_and_regression_models_emit_schema_versions(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "unsupported"
    out_path = tmp_path / "evals" / "unsupported.jsonl"
    trace = import_trace(ROOT / "examples/unsupported-research-agent/trace.json", run_dir)

    finding = detect_trace(trace)[0]
    case = promote_run(trace, run_dir, out_path)
    line = json.loads(out_path.read_text())

    Detection.model_validate(dump_model(finding))
    RegressionCase.model_validate(line)
    assert line["schema_version"] == "flightrec.regression.v1"
    assert case.schema_version == "flightrec.regression.v1"
