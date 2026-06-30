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
from .importers import SUPPORTED_FORMATS, TraceImportError, dump_model, import_trace, load_run, write_json
from .models import FINDING_SCHEMA_VERSION, REGRESSION_SCHEMA_VERSION, REPORT_SCHEMA_VERSION, TRACE_SCHEMA_VERSION, status_for_detections
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
    trace_format: str = typer.Option("generic", "--format", help="Import adapter: generic, gemini-json, or ai-studio-loglike."),
    out: Path = typer.Option(..., "--out", "-o", help="Run directory to write."),
    quiet: bool = typer.Option(False, "--quiet", help="Only print the primary output path."),
    verbose: bool = typer.Option(False, "--verbose", help="Print extra import metadata."),
) -> None:
    if trace_format not in SUPPORTED_FORMATS:
        raise typer.BadParameter(f"Use one of: {', '.join(sorted(SUPPORTED_FORMATS))}.", param_hint="--format")
    trace = _import_trace_or_exit(trace_path, out, trace_format)
    if quiet:
        console.print(out / "trace.json")
        return
    console.print(f"Imported: {trace_path}")
    console.print(f"Format: {trace_format}")
    console.print(f"Run: {out / 'trace.json'}")
    console.print(f"Run id: {trace.run_id or 'unknown-run'}")
    if verbose:
        console.print(f"Events: {len(trace.events)}")
        console.print(f"Schema: {trace.schema_version}")


@app.command()
def report(
    run_dir: Path = typer.Argument(..., help="Imported run directory."),
    html: bool = typer.Option(False, "--html", help="Print the generated HTML path."),
    out_root: Path = typer.Option(Path("reports"), "--out-root", help="Report output root."),
    strict: bool = typer.Option(False, "--strict", help="Exit nonzero when the report status is not PASS."),
    quiet: bool = typer.Option(False, "--quiet", help="Only print the primary report path."),
    verbose: bool = typer.Option(False, "--verbose", help="Print labels and severity details."),
) -> None:
    trace = _load_run_or_exit(run_dir)
    detections = detect_trace(trace)
    paths = generate_reports(run_dir, trace, out_root)
    status = status_for_detections(detections)
    if quiet:
        console.print(paths["timeline_html"] if html else paths["timeline_md"])
        _exit_for_strict(status, strict)
        return
    console.print(f"Status: {status}")
    console.print(f"Markdown: {paths['timeline_md']}")
    if html:
        console.print(f"HTML: {paths['timeline_html']}")
    console.print(f"Detections: {paths['detections']}")
    if verbose:
        _print_detections(detections, verbose=True)
    _exit_for_strict(status, strict)


@app.command()
def detect(
    run_dir: Path = typer.Argument(..., help="Imported run directory."),
    strict: bool = typer.Option(False, "--strict", help="Exit nonzero when status is not PASS."),
    quiet: bool = typer.Option(False, "--quiet", help="Only print the status."),
    verbose: bool = typer.Option(False, "--verbose", help="Print detector code, severity, and details."),
) -> None:
    trace = _load_run_or_exit(run_dir)
    detections = detect_trace(trace)
    write_json(run_dir / "detections.json", [dump_model(detection) for detection in detections])
    status = status_for_detections(detections)
    console.print(status if quiet else f"Status: {status}")
    if not quiet:
        _print_detections(detections, verbose=verbose)
    _exit_for_strict(status, strict)


@app.command()
def replay(
    run_dir: Path = typer.Argument(..., help="Imported run directory."),
    mode: str = typer.Option("mock", "--mode", help="Replay mode: mock or gemini."),
    prompt: Optional[Path] = typer.Option(None, "--prompt", help="Changed prompt/config to replay with."),
    strict: bool = typer.Option(False, "--strict", help="Exit nonzero when replay status is not PASS."),
    quiet: bool = typer.Option(False, "--quiet", help="Only print the replay status."),
    verbose: bool = typer.Option(False, "--verbose", help="Print remaining and new detector labels."),
) -> None:
    trace = _load_run_or_exit(run_dir)
    try:
        result = replay_run(trace, run_dir, mode=mode, prompt_path=prompt)
    except (RuntimeError, ValueError) as exc:
        console.print(f"Error: {exc}", style="red")
        raise typer.Exit(1) from exc
    if quiet:
        console.print(result.after_status)
        _exit_for_strict(result.after_status, strict)
        return
    console.print("Replay:")
    console.print(f"  original: {summarize_original_answer(result.original_final_answer)}")
    console.print(f"  replay: {summarize_replay_answer(result.replay_final_answer)}")
    console.print(f"  before: {result.before_status}")
    console.print(f"  after: {result.after_status}")
    if result.detector_changes["resolved"]:
        console.print("  resolved:")
        for label in result.detector_changes["resolved"]:
            console.print(f"    - {label}")
    if verbose:
        console.print(f"  remaining: {', '.join(result.detector_changes['remaining']) or 'none'}")
        console.print(f"  new: {', '.join(result.detector_changes['new']) or 'none'}")
    _exit_for_strict(result.after_status, strict)


@app.command()
def promote(
    run_dir: Path = typer.Argument(..., help="Imported run directory."),
    out: Path = typer.Option(..., "--out", "-o", help="JSONL regression output path."),
    quiet: bool = typer.Option(False, "--quiet", help="Only print the regression path."),
    verbose: bool = typer.Option(False, "--verbose", help="Print expected failures and required behavior."),
) -> None:
    trace = _load_run_or_exit(run_dir)
    case = promote_run(trace, run_dir, out)
    if quiet:
        console.print(out)
        return
    console.print("Regression test written:")
    console.print(f"  {out}")
    console.print(f"Case: {case.case_id}")
    if verbose:
        console.print(f"Expected failures: {', '.join(case.expected_failures) or 'none'}")
        console.print(f"Required behavior: {case.required_behavior}")


@app.command()
def demo(
    strict: bool = typer.Option(False, "--strict", help="Exit nonzero if any demo replay remains non-PASS."),
    quiet: bool = typer.Option(False, "--quiet", help="Print only case names and statuses."),
    verbose: bool = typer.Option(False, "--verbose", help="Print detector details for each demo case."),
) -> None:
    if not quiet:
        console.print("[bold]Gemini Flight Recorder[/bold]\n")
    cases = [
        {
            "name": "refund false completion",
            "trace": Path("examples/failing-refund-agent/trace.json"),
            "run": Path("runs/failing-refund-agent"),
            "prompt": Path("examples/failing-refund-agent/prompt_tighter.md"),
            "regression": Path("evals/refund_failure_regression.jsonl"),
        },
        {
            "name": "unsupported evidence claim",
            "trace": Path("examples/unsupported-research-agent/trace.json"),
            "run": Path("runs/unsupported-research-agent"),
            "prompt": None,
            "regression": Path("evals/unsupported_evidence_regression.jsonl"),
        },
        {
            "name": "prompt injection followed",
            "trace": Path("examples/prompt-injection-agent/trace.json"),
            "run": Path("runs/prompt-injection-agent"),
            "prompt": None,
            "regression": Path("evals/prompt_injection_regression.jsonl"),
        },
    ]

    replay_statuses: list[str] = []
    for index, case in enumerate(cases, start=1):
        trace_path = case["trace"]
        run_dir = case["run"]
        prompt_path = case["prompt"]
        regression_path = case["regression"]

        trace = import_trace(trace_path, run_dir, "generic")
        detections = detect_trace(trace)
        result = replay_run(trace, run_dir, mode="mock", prompt_path=prompt_path)
        promote_run(trace, run_dir, regression_path)
        report_paths = generate_reports(run_dir, trace, Path("reports"))
        replay_statuses.append(result.after_status)

        if quiet:
            console.print(f"{case['name']}: {status_for_detections(detections)}")
            continue
        console.print(f"{index}. {case['name']}")
        console.print(f"   Imported: {trace_path}")
        console.print(f"   Status: {status_for_detections(detections)}")
        console.print("   Failure labels:")
        for detection in detections:
            console.print(f"     - {detection.label}")
        console.print(f"   Timeline: {report_paths['timeline_html']}")
        console.print(f"   Regression: {regression_path}")
        console.print(f"   Replay: {summarize_original_answer(result.original_final_answer)} -> {summarize_replay_answer(result.replay_final_answer)}")
        if verbose:
            for detection in detections:
                console.print(f"   {detection.code} {detection.severity}: {detection.detail}")
        if index != len(cases):
            console.print("")
    if strict and any(status != "PASS" for status in replay_statuses):
        raise typer.Exit(2)


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


@app.command()
def version() -> None:
    """Print package and schema versions."""
    console.print(f"flightrec {__version__}")
    console.print(f"trace schema: {TRACE_SCHEMA_VERSION}")
    console.print(f"finding schema: {FINDING_SCHEMA_VERSION}")
    console.print(f"report schema: {REPORT_SCHEMA_VERSION}")
    console.print(f"regression schema: {REGRESSION_SCHEMA_VERSION}")


def _load_run_or_exit(run_dir: Path):
    try:
        return load_run(run_dir)
    except TraceImportError as exc:
        console.print(f"Error: {exc}", style="red")
        raise typer.Exit(1) from exc


def _import_trace_or_exit(trace_path: Path, out: Path, trace_format: str):
    try:
        return import_trace(trace_path, out, trace_format)
    except TraceImportError as exc:
        console.print(f"Error: {exc}", style="red")
        raise typer.Exit(1) from exc


def _print_detections(detections, verbose: bool = False) -> None:
    if not detections:
        console.print("Failure labels: none")
        return
    console.print("Failure labels:")
    for detection in detections:
        if verbose:
            console.print(f"  - {detection.label} ({detection.code}, {detection.severity})")
            console.print(f"    {detection.detail}")
        else:
            console.print(f"  - {detection.label}")


def _exit_for_strict(status: str, strict: bool) -> None:
    if strict and status != "PASS":
        raise typer.Exit(2)


def _package_version(package: str) -> str:
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return "not installed"


def main() -> None:
    app()


if __name__ == "__main__":
    main()
