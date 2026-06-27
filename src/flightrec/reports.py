from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from jinja2 import Template

from .detectors import detect_trace
from .importers import dump_model, write_json
from .models import Detection, Trace, status_for_detections


DISPLAY_PRIORITY = {
    "FR001": 0,
    "FR003": 1,
    "FR004": 2,
    "FR002": 3,
    "FR006": 4,
    "FR007": 5,
    "FR005": 6,
    "FR008": 7,
}


def generate_reports(run_dir: Path, trace: Trace, output_root: Path = Path("reports")) -> dict[str, Path]:
    detections = detect_trace(trace)
    report_dir = output_root / run_dir.name
    report_dir.mkdir(parents=True, exist_ok=True)

    annotations = _annotations_by_event(detections)
    replay_summary = _load_json(run_dir / "replay.json")
    regression_summary = _load_json(run_dir / "regression.json")
    timeline = _timeline_payload(trace, detections, annotations, replay_summary, regression_summary)

    paths = {
        "timeline_json": report_dir / "timeline.json",
        "timeline_md": report_dir / "timeline.md",
        "timeline_html": report_dir / "timeline.html",
        "detections": report_dir / "detections.json",
    }
    write_json(paths["timeline_json"], timeline)
    write_json(paths["detections"], [dump_model(detection) for detection in detections])
    paths["timeline_md"].write_text(render_markdown(trace, detections, annotations, replay_summary, regression_summary))
    paths["timeline_html"].write_text(render_html(trace, detections, annotations, replay_summary, regression_summary))
    return paths


def render_markdown(
    trace: Trace,
    detections: list[Detection],
    annotations: dict[int, list[Detection]] | None = None,
    replay_summary: dict[str, Any] | None = None,
    regression_summary: dict[str, Any] | None = None,
) -> str:
    annotations = annotations or _annotations_by_event(detections)
    status = status_for_detections(detections)
    lines = [
        "# Gemini Flight Recorder",
        "",
        f"Failure timeline for `{trace.run_id or 'unknown-run'}`",
        "",
        f"**Status:** `{status}`",
        "",
        "## Top failures",
    ]
    if detections:
        for index, detection in enumerate(_sorted_detections(detections), start=1):
            lines.append(f"{index}. **{detection.label}** - {detection.detail}")
    else:
        lines.append("No failures detected.")

    if replay_summary:
        lines.extend(
            [
                "",
                "## Replay summary",
                "",
                f"- before: `{replay_summary.get('before_status', 'unknown')}`",
                f"- after: `{replay_summary.get('after_status', 'unknown')}`",
                f"- replay: {replay_summary.get('replay_final_answer', '')}",
            ]
        )
    if regression_summary:
        lines.extend(["", "## Regression case", "", f"- path: `{regression_summary.get('path', 'unknown')}`"])

    lines.extend(["", "## Timeline", ""])
    for index, event in enumerate(trace.events):
        event_label = event.type.replace("_", " ")
        lines.append(f"### {index + 1}. {event_label}")
        if event.timestamp:
            lines.append(f"- timestamp: `{event.timestamp}`")
        if event.event_id:
            lines.append(f"- event id: `{event.event_id}`")
        if event.tool_name:
            lines.append(f"- tool: `{event.tool_name}`")
        body = _event_body(event)
        if body:
            lines.append("")
            lines.append("```text")
            lines.append(body)
            lines.append("```")
        for detection in annotations.get(index, []):
            lines.append(f"- detector: `{detection.code}` `{detection.label}` ({detection.severity})")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_html(
    trace: Trace,
    detections: list[Detection],
    annotations: dict[int, list[Detection]] | None = None,
    replay_summary: dict[str, Any] | None = None,
    regression_summary: dict[str, Any] | None = None,
) -> str:
    annotations = annotations or _annotations_by_event(detections)
    template = Template(HTML_TEMPLATE)
    return template.render(
        trace=trace,
        detections=_sorted_detections(detections),
        status=status_for_detections(detections),
        annotations=annotations,
        event_body=_event_body,
        replay_summary=replay_summary,
        regression_summary=regression_summary,
    )


def _timeline_payload(
    trace: Trace,
    detections: list[Detection],
    annotations: dict[int, list[Detection]],
    replay_summary: dict[str, Any] | None,
    regression_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "run_id": trace.run_id,
        "source": trace.source,
        "model": trace.model,
        "task": trace.task,
        "status": status_for_detections(detections),
        "detections": [dump_model(detection) for detection in detections],
        "replay": replay_summary,
        "regression": regression_summary,
        "events": [
            {
                **dump_model(event),
                "annotations": [dump_model(detection) for detection in annotations.get(index, [])],
            }
            for index, event in enumerate(trace.events)
        ],
    }


def _annotations_by_event(detections: list[Detection]) -> dict[int, list[Detection]]:
    annotations: dict[int, list[Detection]] = defaultdict(list)
    for detection in detections:
        for event_index in detection.event_indices:
            annotations[event_index].append(detection)
    return annotations


def _sorted_detections(detections: list[Detection]) -> list[Detection]:
    return sorted(detections, key=lambda detection: DISPLAY_PRIORITY.get(detection.code, 99))


def _event_body(event: Any) -> str:
    if event.type == "model_call":
        parts = []
        if event.input:
            parts.append(f"input: {event.input}")
        if event.output:
            parts.append(f"output: {event.output}")
        return "\n".join(parts)
    if event.type == "tool_call":
        return f"args: {event.args}"
    if event.type == "tool_result":
        if event.error:
            return f"error: {event.error}"
        return f"result: {event.result}"
    if event.type == "final_answer":
        return event.content or event.output or ""
    return event.content or event.output or event.input or ""


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Gemini Flight Recorder - {{ trace.run_id or "timeline" }}</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #17212b;
      --muted: #5c6670;
      --line: #d8dde3;
      --panel: #ffffff;
      --soft: #f5f7fa;
      --blue: #1f6feb;
      --red: #bf1d1d;
      --amber: #986800;
      --green: #137333;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: var(--ink);
      background: #eef2f7;
      font: 15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    header {
      background: #ffffff;
      border-bottom: 1px solid var(--line);
    }
    .wrap {
      max-width: 1120px;
      margin: 0 auto;
      padding: 28px 24px;
    }
    h1 {
      margin: 0 0 8px;
      font-size: 30px;
      letter-spacing: 0;
    }
    h2 {
      margin: 28px 0 12px;
      font-size: 18px;
      letter-spacing: 0;
    }
    p { margin: 0 0 10px; }
    .subhead {
      color: var(--muted);
      font-size: 17px;
    }
    .summary {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 280px;
      gap: 20px;
      align-items: start;
      margin-top: 24px;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
    }
    .status {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 6px 10px;
      border-radius: 999px;
      font-weight: 700;
      color: #fff;
      background: var(--red);
      letter-spacing: .02em;
      font-size: 12px;
    }
    .status.pass { background: var(--green); }
    .status.review { background: var(--amber); }
    ol {
      margin: 12px 0 0;
      padding-left: 22px;
    }
    li { margin: 8px 0; }
    .meta-grid {
      display: grid;
      gap: 10px;
      color: var(--muted);
      font-size: 13px;
    }
    .meta-grid strong {
      display: block;
      color: var(--ink);
      font-size: 14px;
      margin-bottom: 2px;
    }
    .artifact-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
      margin-top: 16px;
    }
    .artifact {
      background: var(--soft);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      color: var(--muted);
      font-size: 13px;
    }
    .artifact strong {
      display: block;
      color: var(--ink);
      margin-bottom: 4px;
    }
    .timeline {
      position: relative;
      display: grid;
      gap: 14px;
      margin-top: 14px;
    }
    .event {
      position: relative;
      display: grid;
      grid-template-columns: 130px minmax(0, 1fr);
      gap: 16px;
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
    }
    .event-kind {
      color: var(--blue);
      font-weight: 700;
      text-transform: uppercase;
      font-size: 12px;
      letter-spacing: .06em;
    }
    .timestamp {
      color: var(--muted);
      font-size: 12px;
      word-break: break-word;
    }
    .event-main h3 {
      margin: 0 0 8px;
      font-size: 16px;
    }
    pre {
      margin: 10px 0 0;
      padding: 12px;
      overflow-x: auto;
      white-space: pre-wrap;
      background: var(--soft);
      border: 1px solid var(--line);
      border-radius: 6px;
      font: 13px/1.45 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    }
    .badges {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 12px;
    }
    .badge {
      display: inline-flex;
      padding: 4px 8px;
      border-radius: 999px;
      border: 1px solid var(--line);
      color: var(--ink);
      background: #fff8e5;
      font-size: 12px;
      font-weight: 650;
    }
    .badge.high { background: #ffe9e9; border-color: #f0b3b3; color: #8f1111; }
    .badge.medium { background: #fff8e5; border-color: #ecd48b; color: #6f4d00; }
    .badge.low { background: #edf7ee; border-color: #b7dfbd; color: #0c5c2a; }
    @media (max-width: 780px) {
      .summary { grid-template-columns: 1fr; }
      .artifact-grid { grid-template-columns: 1fr; }
      .event { grid-template-columns: 1fr; gap: 8px; }
      .wrap { padding: 22px 16px; }
    }
  </style>
</head>
<body>
  <header>
    <div class="wrap">
      <h1>Gemini Flight Recorder</h1>
      <p class="subhead">Failure timeline for {{ trace.run_id or "unknown-run" }}</p>
      <div class="summary">
        <section class="panel">
          <span class="status {% if status == 'PASS' %}pass{% elif status == 'REVIEW_RECOMMENDED' %}review{% endif %}">Status: {{ status }}</span>
          <div class="artifact-grid">
            <div class="artifact"><strong>Run id</strong>{{ trace.run_id or "unknown-run" }}</div>
            <div class="artifact"><strong>Model / source</strong>{{ trace.model }} / {{ trace.source }}</div>
          </div>
          <h2>Top failures</h2>
          {% if detections %}
          <ol>
            {% for detection in detections[:5] %}
            <li>{{ detection.detail }}</li>
            {% endfor %}
          </ol>
          {% else %}
          <p>No failures detected.</p>
          {% endif %}
          {% if replay_summary or regression_summary %}
          <div class="artifact-grid">
            {% if replay_summary %}
            <div class="artifact">
              <strong>Replay</strong>
              {{ replay_summary.before_status }} -> {{ replay_summary.after_status }}<br>
              {{ replay_summary.replay_final_answer }}
            </div>
            {% endif %}
            {% if regression_summary %}
            <div class="artifact">
              <strong>Regression case</strong>
              {{ regression_summary.path }}
            </div>
            {% endif %}
          </div>
          {% endif %}
        </section>
        <aside class="panel meta-grid">
          <div><strong>Run id</strong>{{ trace.run_id or "unknown-run" }}</div>
          <div><strong>Model</strong>{{ trace.model }}</div>
          <div><strong>Source</strong>{{ trace.source }}</div>
          <div><strong>Task</strong>{{ trace.task }}</div>
        </aside>
      </div>
    </div>
  </header>
  <main class="wrap">
    <h2>Timeline</h2>
    <section class="timeline">
      {% for event in trace.events %}
      {% set index = loop.index0 %}
      <article class="event">
        <div>
          <div class="event-kind">{{ event.type.replace("_", " ") }}</div>
          {% if event.timestamp %}<div class="timestamp">{{ event.timestamp }}</div>{% endif %}
          {% if event.event_id %}<div class="timestamp">{{ event.event_id }}</div>{% endif %}
        </div>
        <div class="event-main">
          <h3>{% if event.tool_name %}{{ event.tool_name }}{% elif event.role %}{{ event.role }}{% else %}{{ event.type.replace("_", " ").title() }}{% endif %}</h3>
          {% set body = event_body(event) %}
          {% if body %}<pre>{{ body }}</pre>{% endif %}
          {% if annotations.get(index) %}
          <div class="badges">
            {% for detection in annotations[index] %}
            <span class="badge {{ detection.severity }}">{{ detection.code }} {{ detection.label }}</span>
            {% endfor %}
          </div>
          {% endif %}
        </div>
      </article>
      {% endfor %}
    </section>
  </main>
</body>
</html>
"""
