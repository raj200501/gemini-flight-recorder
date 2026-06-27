from __future__ import annotations

import importlib.metadata
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .detectors import detect_trace
from .importers import dump_model, import_trace, load_run, write_json
from .models import status_for_detections
from .promote import promote_run
from .replay import replay_run, summarize_original_answer, summarize_replay_answer
from .reports import generate_reports


app = typer.Typer(
    help="Turn failed Gemini app traces into timelines, replays, and regression tests.",
    no_args_is_help=True,
)
console = Console()


@app.command("import")
def import_command(
    trace_path: Path = typer.Argument(..., help="Public JSON trace to import."),
    out: Path = typer.Option(..., "--out", "-o", help="Run directory to write."),
) -> None:
    trace = import_trace(trace_path, out)
    console.print(f"Imported: {trace_path}")
    console.print(f"Run: {out / 'trace.json'}")
    console.print(f"Run id: {trace.run_id or 'unknown-run'}")


@app.command()
def report(
    run_dir: Path = typer.Argument(..., help="Imported run directory."),
    html: bool = typer.Option(False, "--html", help="Print the generated HTML path."),
    out_root: Path = typer.Option(Path("reports"), "--out-root", help="Report output root."),
) -> None:
    trace = load_run(run_dir)
    paths = generate_reports(run_dir, trace, out_root)
    console.print(f"Status: {status_for_detections(detect_trace(trace))}")
    console.print(f"Markdown: {paths['timeline_md']}")
    if html:
        console.print(f"HTML: {paths['timeline_html']}")
    console.print(f"Detections: {paths['detections']}")


@app.command()
def detect(run_dir: Path = typer.Argument(..., help="Imported run directory.")) -> None:
    trace = load_run(run_dir)
    detections = detect_trace(trace)
    write_json(run_dir / "detections.json", [dump_model(detection) for detection in detections])
    console.print(f"Status: {status_for_detections(detections)}")
    if not detections:
        console.print("Failure labels: none")
        return
    console.print("Failure labels:")
    for detection in detections:
        console.print(f"  - {detection.label}")


@app.command()
def replay(
    run_dir: Path = typer.Argument(..., help="Imported run directory."),
    mode: str = typer.Option("mock", "--mode", help="Replay mode: mock or gemini."),
    prompt: Optional[Path] = typer.Option(None, "--prompt", help="Changed prompt/config to replay with."),
) -> None:
    trace = load_run(run_dir)
    result = replay_run(trace, run_dir, mode=mode, prompt_path=prompt)
    console.print("Replay:")
    console.print(f"  original: {summarize_original_answer(result.original_final_answer)}")
    console.print(f"  replay: {summarize_replay_answer(result.replay_final_answer)}")
    console.print(f"  before: {result.before_status}")
    console.print(f"  after: {result.after_status}")
    if result.detector_changes["resolved"]:
        console.print("  resolved:")
        for label in result.detector_changes["resolved"]:
            console.print(f"    - {label}")


@app.command()
def promote(
    run_dir: Path = typer.Argument(..., help="Imported run directory."),
    out: Path = typer.Option(..., "--out", "-o", help="JSONL regression output path."),
) -> None:
    trace = load_run(run_dir)
    case = promote_run(trace, run_dir, out)
    console.print("Regression test written:")
    console.print(f"  {out}")
    console.print(f"Case: {case.case_id}")


@app.command()
def demo() -> None:
    console.print("[bold]Gemini Flight Recorder[/bold]\n")
    trace_path = Path("examples/failing-refund-agent/trace.json")
    run_dir = Path("runs/failing-refund-agent")
    prompt_path = Path("examples/failing-refund-agent/prompt_tighter.md")
    regression_path = Path("evals/refund_failure_regression.jsonl")

    trace = import_trace(trace_path, run_dir)
    detections = detect_trace(trace)
    report_paths = generate_reports(run_dir, trace, Path("reports"))
    result = replay_run(trace, run_dir, mode="mock", prompt_path=prompt_path)
    promote_run(trace, run_dir, regression_path)

    console.print(f"Imported: {trace_path}")
    console.print(f"Status: {status_for_detections(detections)}")
    console.print("Failure labels:")
    for detection in detections:
        console.print(f"  - {detection.label}")
    console.print("\nTimeline:")
    console.print(f"  {report_paths['timeline_html']}")
    console.print(f"  {report_paths['timeline_md']}")
    console.print("\nReplay:")
    console.print(f"  original: {summarize_original_answer(result.original_final_answer)}")
    console.print(f"  replay: {summarize_replay_answer(result.replay_final_answer)}")
    console.print("\nRegression test written:")
    console.print(f"  {regression_path}")


@app.command()
def doctor() -> None:
    table = Table(title="Gemini Flight Recorder Doctor")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Detail")
    table.add_row("flightrec", "ok", f"version {__version__}")
    table.add_row("python", "ok", sys.version.split()[0])
    for package in ("typer", "rich", "pydantic", "jinja2", "pytest"):
        table.add_row(package, "ok", _package_version(package))
    table.add_row("gemini mode", "optional", "set GEMINI_API_KEY to use live Gemini replay")
    table.add_row("mock replay", "ok", "offline demo mode available")
    console.print(table)


def _package_version(package: str) -> str:
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return "not installed"


def main() -> None:
    app()


if __name__ == "__main__":
    main()

