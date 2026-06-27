import json
from pathlib import Path

from typer.testing import CliRunner

from flightrec.cli import app
from flightrec.importers import import_trace
from flightrec.promote import promote_run
from flightrec.replay import replay_run
from flightrec.reports import generate_reports


ROOT = Path(__file__).resolve().parents[1]


def test_report_generation_writes_html_markdown_json(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "refund"
    report_root = tmp_path / "reports"
    trace = import_trace(ROOT / "examples/failing-refund-agent/trace.json", run_dir)
    replay_run(trace, run_dir, mode="mock", prompt_path=ROOT / "examples/failing-refund-agent/prompt_tighter.md")
    promote_run(trace, run_dir, tmp_path / "evals" / "refund.jsonl")

    paths = generate_reports(run_dir, trace, report_root)

    assert paths["timeline_html"].exists()
    assert paths["timeline_md"].exists()
    assert paths["timeline_json"].exists()
    assert paths["detections"].exists()
    assert "Gemini Flight Recorder" in paths["timeline_html"].read_text()
    assert "false_completion" in paths["timeline_html"].read_text()
    assert "Replay" in paths["timeline_html"].read_text()
    assert "Regression case" in paths["timeline_html"].read_text()


def test_mock_replay_resolves_refund_completion_failures(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "refund"
    trace = import_trace(ROOT / "examples/failing-refund-agent/trace.json", run_dir)

    result = replay_run(trace, run_dir, mode="mock", prompt_path=ROOT / "examples/failing-refund-agent/prompt_tighter.md")

    assert result.before_status == "FAILURE_DETECTED"
    assert result.after_status == "PASS"
    assert "false_completion" in result.detector_changes["resolved"]
    assert "tool_error_ignored" in result.detector_changes["resolved"]
    assert "could not be confirmed" in result.replay_final_answer


def test_mock_replay_corrections_are_label_specific(tmp_path: Path) -> None:
    cases = [
        ("unsupported-research-agent", "cannot be called verified"),
        ("prompt-injection-agent", "untrusted data"),
        ("repeated-tool-loop", "kept failing"),
    ]

    for example, expected_text in cases:
        run_dir = tmp_path / "runs" / example
        trace = import_trace(ROOT / "examples" / example / "trace.json", run_dir)
        result = replay_run(trace, run_dir, mode="mock")

        assert expected_text in result.replay_final_answer
        assert result.after_status == "PASS"


def test_promote_writes_jsonl_regression_case(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "refund"
    out_path = tmp_path / "evals" / "refund.jsonl"
    trace = import_trace(ROOT / "examples/failing-refund-agent/trace.json", run_dir)
    replay_run(trace, run_dir, mode="mock", prompt_path=ROOT / "examples/failing-refund-agent/prompt_tighter.md")

    case = promote_run(trace, run_dir, out_path)
    line = json.loads(out_path.read_text())

    assert case.case_id == "refund-tool-timeout-false-completion"
    assert line["case_id"] == "refund-tool-timeout-false-completion"
    assert "false_completion" in line["expected_failures"]
    assert "The assistant must say the refund could not be confirmed" in line["required_behavior"]


def test_promote_writes_useful_evidence_and_injection_cases(tmp_path: Path) -> None:
    cases = {
        "unsupported-research-agent": "verified, cited, grounded, or source-backed",
        "prompt-injection-agent": "untrusted data",
    }

    for example, expected_behavior in cases.items():
        run_dir = tmp_path / "runs" / example
        out_path = tmp_path / "evals" / f"{example}.jsonl"
        trace = import_trace(ROOT / "examples" / example / "trace.json", run_dir)
        replay_run(trace, run_dir, mode="mock")

        promote_run(trace, run_dir, out_path)
        line = json.loads(out_path.read_text())

        assert line["expected_failures"]
        assert expected_behavior in line["required_behavior"]
        assert (run_dir / "regression.json").exists()


def test_cli_demo_runs_offline(monkeypatch) -> None:
    monkeypatch.chdir(ROOT)
    runner = CliRunner()

    result = runner.invoke(app, ["demo"])

    assert result.exit_code == 0, result.output
    assert "Gemini Flight Recorder" in result.output
    assert "Status: FAILURE_DETECTED" in result.output
    assert "reports/failing-refund-agent/timeline.html" in result.output
    assert "evals/refund_failure_regression.jsonl" in result.output
    assert "unsupported evidence claim" in result.output
    assert "prompt injection followed" in result.output
    assert "reports/unsupported-research-agent/timeline.html" in result.output
    assert "reports/prompt-injection-agent/timeline.html" in result.output


def test_cli_import_format_option(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(ROOT)
    runner = CliRunner()
    out_dir = tmp_path / "runs" / "refund"

    result = runner.invoke(
        app,
        [
            "import",
            "examples/failing-refund-agent/trace.json",
            "--format",
            "generic",
            "--out",
            str(out_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Format: generic" in result.output
    assert (out_dir / "trace.json").exists()
