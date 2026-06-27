from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import Trace, TraceEvent


TRACE_FILENAME = "trace.json"


def _json_default(value: Any) -> str:
    return str(value)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=False, default=_json_default) + "\n")


def dump_model(model: Any) -> dict[str, Any]:
    return model.model_dump(mode="json", exclude_none=True)


def load_trace(path: Path) -> Trace:
    data = json.loads(path.read_text())
    trace = Trace.model_validate(data)
    return _normalize_trace(trace)


def load_run(run_path: Path) -> Trace:
    if run_path.is_dir():
        return load_trace(run_path / TRACE_FILENAME)
    return load_trace(run_path)


def import_trace(trace_path: Path, out_dir: Path) -> Trace:
    trace = load_trace(trace_path)
    trace.metadata = {**trace.metadata, "imported_from": str(trace_path)}
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / TRACE_FILENAME, dump_model(trace))
    return trace


def _normalize_trace(trace: Trace) -> Trace:
    normalized_events: list[TraceEvent] = []
    for index, event in enumerate(trace.events):
        metadata = dict(event.metadata)
        metadata.setdefault("index", index)
        event.metadata = metadata
        normalized_events.append(event)
    trace.events = normalized_events
    return trace

