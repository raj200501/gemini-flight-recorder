from pathlib import Path

import pytest
from typer.testing import CliRunner

from flightrec.cli import app
from flightrec.detectors import detect_trace
from flightrec.importers import TraceImportError, import_trace, load_trace


ROOT = Path(__file__).resolve().parents[1]


def test_malformed_json_raises_clean_import_error(tmp_path: Path) -> None:
    trace_path = tmp_path / "bad.json"
    trace_path.write_text('{"run_id": "bad",')

    with pytest.raises(TraceImportError, match="Malformed JSON"):
        load_trace(trace_path)


def test_missing_file_raises_clean_import_error(tmp_path: Path) -> None:
    with pytest.raises(TraceImportError, match="Trace file not found"):
        load_trace(tmp_path / "missing.json")


def test_non_object_json_raises_clean_import_error(tmp_path: Path) -> None:
    trace_path = tmp_path / "list.json"
    trace_path.write_text("[]")

    with pytest.raises(TraceImportError, match="Trace root must be a JSON object"):
        load_trace(trace_path)


def test_weird_unicode_trace_does_not_crash(tmp_path: Path) -> None:
    trace_path = tmp_path / "unicode.json"
    trace_path.write_text(
        """
{
  "run_id": "unicode-001",
  "request_id": "req-unicode-001",
  "source": "gemini-api",
  "model": "gemini-2.5-flash",
  "task": "Summarize unusual text",
  "events": [
    {"type": "model_call", "event_id": "u-1", "timestamp": "2026-01-18T10:00:00Z", "output": "snowman ☃ and accented café text"},
    {"type": "final_answer", "event_id": "u-2", "timestamp": "2026-01-18T10:00:01Z", "content": "The text mentions a snowman and cafe spelling variants."}
  ]
}
""".strip()
    )

    trace = load_trace(trace_path)

    assert detect_trace(trace) == []


def test_empty_trace_has_clear_pass_result(tmp_path: Path) -> None:
    trace_path = tmp_path / "empty.json"
    trace_path.write_text(
        '{"run_id": "empty-001", "source": "gemini-api", "model": "gemini-2.5-flash", "task": "", "events": []}'
    )

    trace = load_trace(trace_path)

    assert detect_trace(trace) == []


def test_random_text_file_does_not_crash_cli(tmp_path: Path) -> None:
    trace_path = tmp_path / "random.txt"
    trace_path.write_text("not json")
    runner = CliRunner()

    result = runner.invoke(app, ["import", str(trace_path), "--out", str(tmp_path / "run")])

    assert result.exit_code == 1
    assert "Malformed JSON" in result.output


def test_cli_strict_quiet_verbose_and_version(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(ROOT)
    runner = CliRunner()
    run_dir = tmp_path / "runs" / "refund"
    trace = import_trace(ROOT / "examples/failing-refund-agent/trace.json", run_dir)
    assert trace.run_id == "refund-001"

    normal = runner.invoke(app, ["detect", str(run_dir)])
    strict = runner.invoke(app, ["detect", str(run_dir), "--strict"])
    quiet = runner.invoke(app, ["detect", str(run_dir), "--quiet"])
    verbose = runner.invoke(app, ["detect", str(run_dir), "--verbose"])
    version = runner.invoke(app, ["version"])

    assert normal.exit_code == 0
    assert strict.exit_code == 2
    assert quiet.exit_code == 0
    assert quiet.output.strip() == "FAILURE_DETECTED"
    assert verbose.exit_code == 0
    assert "FR001" in verbose.output
    assert version.exit_code == 0
    assert "flightrec 0.1.0" in version.output
    assert "trace schema: flightrec.trace.v1" in version.output
