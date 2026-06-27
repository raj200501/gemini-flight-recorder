from pathlib import Path

from flightrec.importers import import_trace, load_trace


ROOT = Path(__file__).resolve().parents[1]


def test_importing_public_json_trace(tmp_path: Path) -> None:
    out_dir = tmp_path / "runs" / "refund"

    trace = import_trace(ROOT / "examples/failing-refund-agent/trace.json", out_dir)

    assert trace.run_id == "refund-001"
    assert trace.source == "gemini-api"
    assert trace.model == "gemini-2.5-flash"
    assert (out_dir / "trace.json").exists()


def test_normalizing_events_adds_indices() -> None:
    trace = load_trace(ROOT / "examples/failing-refund-agent/trace.json")

    assert trace.events[0].metadata["index"] == 0
    assert trace.events[-1].metadata["index"] == 5
    assert trace.tool_calls[0].tool_name == "get_all_customers"
    assert trace.tool_results[-1].failed is True

