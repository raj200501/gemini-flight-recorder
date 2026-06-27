from pathlib import Path

from flightrec.importers import import_trace, load_trace


ROOT = Path(__file__).resolve().parents[1]


def test_importing_public_json_trace(tmp_path: Path) -> None:
    out_dir = tmp_path / "runs" / "refund"

    trace = import_trace(ROOT / "examples/failing-refund-agent/trace.json", out_dir, "generic")

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


def test_gemini_json_import_format(tmp_path: Path) -> None:
    trace_path = tmp_path / "gemini.json"
    trace_path.write_text(
        """
{
  "run_id": "gemini-json-001",
  "model": "gemini-2.5-flash",
  "contents": [
    {"role": "user", "parts": [{"text": "Summarize the incident."}]}
  ],
  "candidates": [
    {"content": {"parts": [{"text": "The incident was summarized."}]}}
  ]
}
""".strip()
    )

    trace = import_trace(trace_path, tmp_path / "run", "gemini-json")

    assert trace.run_id == "gemini-json-001"
    assert trace.source == "gemini-json"
    assert trace.messages[0].content == "Summarize the incident."
    assert trace.final_answer == "The incident was summarized."


def test_ai_studio_loglike_import_format(tmp_path: Path) -> None:
    trace_path = tmp_path / "ai-studio.json"
    trace_path.write_text(
        """
{
  "run_id": "studio-001",
  "model": "gemini-2.5-flash",
  "task": "Check order O123",
  "logs": [
    {"kind": "user", "text": "Check order O123."},
    {"kind": "tool_call", "name": "lookup_order", "args": {"order_id": "O123"}},
    {"kind": "tool_result", "name": "lookup_order", "result": {"status": "pending"}},
    {"kind": "final", "text": "Order O123 is pending."}
  ]
}
""".strip()
    )

    trace = import_trace(trace_path, tmp_path / "run", "ai-studio-loglike")

    assert trace.run_id == "studio-001"
    assert trace.source == "ai-studio-loglike"
    assert trace.tool_calls[0].tool_name == "lookup_order"
    assert trace.final_answer == "Order O123 is pending."
