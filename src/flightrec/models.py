from __future__ import annotations

import os
from typing import Any, Literal

os.environ.setdefault("PYDANTIC_DISABLE_PLUGINS", "1")

from pydantic import BaseModel, ConfigDict, Field, field_validator


Severity = Literal["low", "medium", "high"]
Status = Literal["PASS", "REVIEW_RECOMMENDED", "FAILURE_DETECTED"]
TRACE_SCHEMA_VERSION = "flightrec.trace.v1"
FINDING_SCHEMA_VERSION = "flightrec.finding.v1"
REPORT_SCHEMA_VERSION = "flightrec.report.v1"
REGRESSION_SCHEMA_VERSION = "flightrec.regression.v1"


class Message(BaseModel):
    model_config = ConfigDict(extra="allow")

    role: str
    content: str = ""


class TraceEvent(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str
    event_id: str | None = None
    timestamp: str | None = None
    role: str | None = None
    content: str | None = None
    input: str | None = None
    output: str | None = None
    tool_name: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)
    result: Any | None = None
    error: str | None = None
    source_name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("args", mode="before")
    @classmethod
    def normalize_args(cls, value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        return {"value": value}


class ToolCall(BaseModel):
    tool_name: str
    args: dict[str, Any] = Field(default_factory=dict)
    event_index: int


class ToolResult(BaseModel):
    tool_name: str
    result: Any | None = None
    error: str | None = None
    event_index: int

    @property
    def failed(self) -> bool:
        if self.error:
            return True
        blob = str(self.result or "").lower()
        return any(word in blob for word in ("error", "failed", "denied", "timeout"))


class Trace(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: str = TRACE_SCHEMA_VERSION
    run_id: str | None = None
    request_id: str | None = None
    source: str = "unknown"
    model: str = "unknown"
    task: str = ""
    messages: list[Message] = Field(default_factory=list)
    events: list[TraceEvent] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def final_answer(self) -> str:
        for event in reversed(self.events):
            if event.type == "final_answer":
                return event.content or event.output or ""
        return ""

    @property
    def tool_calls(self) -> list[ToolCall]:
        return [
            ToolCall(tool_name=event.tool_name or "", args=event.args, event_index=index)
            for index, event in enumerate(self.events)
            if event.type == "tool_call"
        ]

    @property
    def tool_results(self) -> list[ToolResult]:
        return [
            ToolResult(
                tool_name=event.tool_name or "",
                result=event.result,
                error=event.error,
                event_index=index,
            )
            for index, event in enumerate(self.events)
            if event.type == "tool_result"
        ]


class Detection(BaseModel):
    schema_version: str = FINDING_SCHEMA_VERSION
    code: str
    label: str
    severity: Severity
    title: str
    detail: str
    event_indices: list[int] = Field(default_factory=list)
    recommendation: str = ""


class ReplayResult(BaseModel):
    schema_version: str = "flightrec.replay.v1"
    run_id: str
    mode: str
    original_final_answer: str
    replay_final_answer: str
    changed_prompt: str | None = None
    detector_changes: dict[str, list[str]]
    before_status: Status
    after_status: Status
    before_labels: list[str]
    after_labels: list[str]


class RegressionCase(BaseModel):
    schema_version: str = REGRESSION_SCHEMA_VERSION
    case_id: str
    task: str
    original_trace: str
    expected_failures: list[str]
    must_not_claim: list[str]
    required_behavior: str
    suggested_prompt: str | None = None
    source_run_id: str | None = None


def status_for_detections(detections: list[Detection]) -> Status:
    if any(d.severity == "high" for d in detections):
        return "FAILURE_DETECTED"
    if detections:
        return "REVIEW_RECOMMENDED"
    return "PASS"
