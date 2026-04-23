from typing import Literal

from pydantic import BaseModel, Field


ToolMode = Literal["configured", "mock", "unavailable"]
ToolRunStatus = Literal["executed", "previewed", "skipped", "error"]


class ToolStatus(BaseModel):
    name: str
    label: str
    mode: ToolMode
    configured: bool
    available: bool
    details: str


class ToolExecutionResult(BaseModel):
    name: str
    mode: ToolMode
    status: ToolRunStatus
    message: str
    artifact_ref: str | None = None
    external_id: str | None = None


class ToolchainReport(BaseModel):
    statuses: list[ToolStatus] = Field(default_factory=list)
    results: list[ToolExecutionResult] = Field(default_factory=list)
