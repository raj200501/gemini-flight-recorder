from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import Message, Trace, TraceEvent


TRACE_FILENAME = "trace.json"


def _json_default(value: Any) -> str:
    return str(value)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=False, default=_json_default) + "\n")


def dump_model(model: Any) -> dict[str, Any]:
    return model.model_dump(mode="json", exclude_none=True)


SUPPORTED_FORMATS = {"generic", "gemini-json", "ai-studio-loglike"}


def load_trace(path: Path, trace_format: str = "generic") -> Trace:
    data = json.loads(path.read_text())
    trace = normalize_trace_data(data, trace_format)
    return _normalize_trace(trace)


def load_run(run_path: Path) -> Trace:
    if run_path.is_dir():
        return load_trace(run_path / TRACE_FILENAME)
    return load_trace(run_path)


def import_trace(trace_path: Path, out_dir: Path, trace_format: str = "generic") -> Trace:
    trace = load_trace(trace_path, trace_format)
    trace.metadata = {
        **trace.metadata,
        "imported_from": str(trace_path),
        "import_format": trace_format,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / TRACE_FILENAME, dump_model(trace))
    return trace


def normalize_trace_data(data: dict[str, Any], trace_format: str = "generic") -> Trace:
    if trace_format not in SUPPORTED_FORMATS:
        choices = ", ".join(sorted(SUPPORTED_FORMATS))
        raise ValueError(f"Unsupported import format '{trace_format}'. Use one of: {choices}.")
    if trace_format == "generic":
        return _from_generic(data)
    if trace_format == "gemini-json":
        return _from_gemini_json(data)
    return _from_ai_studio_loglike(data)


def _normalize_trace(trace: Trace) -> Trace:
    normalized_events: list[TraceEvent] = []
    for index, event in enumerate(trace.events):
        metadata = dict(event.metadata)
        metadata.setdefault("index", index)
        event.metadata = metadata
        normalized_events.append(event)
    trace.events = normalized_events
    return trace


def _from_generic(data: dict[str, Any]) -> Trace:
    return Trace.model_validate(data)


def _from_gemini_json(data: dict[str, Any]) -> Trace:
    if "events" in data:
        normalized = {**data, "source": data.get("source", "gemini-json")}
        return Trace.model_validate(normalized)

    request = data.get("request", {})
    run_id = data.get("run_id") or data.get("id") or request.get("run_id") or request.get("id")
    task = data.get("task") or request.get("task") or _first_text(data.get("contents", []))
    messages = _messages_from_contents(data.get("contents", []))
    final_answer = _candidate_text(data)
    events = [
        TraceEvent(
            type="model_call",
            input=task,
            output=final_answer,
            metadata={"adapter": "gemini-json"},
        ),
        TraceEvent(type="final_answer", content=final_answer),
    ]
    return Trace(
        run_id=run_id,
        request_id=data.get("request_id") or request.get("request_id"),
        source=data.get("source", "gemini-json"),
        model=data.get("model") or request.get("model") or "gemini",
        task=task,
        messages=messages,
        events=events,
        metadata={"adapter": "gemini-json"},
    )


def _from_ai_studio_loglike(data: dict[str, Any]) -> Trace:
    if "events" in data:
        normalized = {**data, "source": data.get("source", "ai-studio-loglike")}
        return Trace.model_validate(normalized)

    raw_events = data.get("log") or data.get("logs") or data.get("steps") or []
    events: list[TraceEvent] = []
    messages: list[Message] = []
    for index, raw in enumerate(raw_events):
        kind = raw.get("type") or raw.get("kind") or raw.get("event") or "event"
        text = raw.get("content") or raw.get("text") or raw.get("message") or raw.get("output") or ""
        if kind in {"user", "user_message"}:
            messages.append(Message(role="user", content=text))
            events.append(TraceEvent(type="user_message", content=text, event_id=raw.get("id"), timestamp=raw.get("timestamp")))
        elif kind in {"tool_call", "function_call"}:
            events.append(
                TraceEvent(
                    type="tool_call",
                    event_id=raw.get("id") or f"log-{index}",
                    timestamp=raw.get("timestamp"),
                    tool_name=raw.get("tool_name") or raw.get("name"),
                    args=raw.get("args") or raw.get("arguments") or {},
                )
            )
        elif kind in {"tool_result", "function_response"}:
            events.append(
                TraceEvent(
                    type="tool_result",
                    event_id=raw.get("id") or f"log-{index}",
                    timestamp=raw.get("timestamp"),
                    tool_name=raw.get("tool_name") or raw.get("name"),
                    result=raw.get("result") or raw.get("response"),
                    error=raw.get("error"),
                )
            )
        elif kind in {"final", "final_answer", "assistant_final"}:
            events.append(TraceEvent(type="final_answer", content=text, event_id=raw.get("id"), timestamp=raw.get("timestamp")))
        else:
            events.append(
                TraceEvent(
                    type=kind,
                    content=text,
                    event_id=raw.get("id"),
                    timestamp=raw.get("timestamp"),
                    metadata={"adapter": "ai-studio-loglike"},
                )
            )

    return Trace(
        run_id=data.get("run_id") or data.get("id"),
        request_id=data.get("request_id"),
        source=data.get("source", "ai-studio-loglike"),
        model=data.get("model", "gemini"),
        task=data.get("task") or (messages[0].content if messages else ""),
        messages=messages,
        events=events,
        metadata={"adapter": "ai-studio-loglike"},
    )


def _messages_from_contents(contents: Any) -> list[Message]:
    messages: list[Message] = []
    if not isinstance(contents, list):
        return messages
    for item in contents:
        role = item.get("role", "user") if isinstance(item, dict) else "user"
        messages.append(Message(role=role, content=_content_text(item)))
    return messages


def _candidate_text(data: dict[str, Any]) -> str:
    candidates = data.get("candidates") or []
    if candidates:
        return _content_text(candidates[0].get("content", candidates[0]))
    return data.get("output") or data.get("final_answer") or data.get("text") or ""


def _first_text(contents: Any) -> str:
    if isinstance(contents, list) and contents:
        return _content_text(contents[0])
    return ""


def _content_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return str(value or "")
    if "text" in value:
        return str(value["text"])
    if "content" in value and isinstance(value["content"], str):
        return value["content"]
    parts = value.get("parts") or []
    if isinstance(parts, list):
        return "\n".join(str(part.get("text", part) if isinstance(part, dict) else part) for part in parts)
    return ""
