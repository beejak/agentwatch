"""API response schemas for WatchTower REST API."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class HealthStatus(BaseModel):
    status: str             # "ok" or "degraded"
    clickhouse: str
    redis: str
    neo4j: str
    postgres: str


class SpanResponse(BaseModel):
    trace_id: str
    span_id: Optional[str] = None
    agent_id: Optional[str] = None
    action: Optional[str] = None
    status: Optional[str] = None
    timestamp: Optional[float] = None
    duration_ms: Optional[float] = None
    summary: Optional[str] = None


class TraceResponse(BaseModel):
    trace_id: str
    span_count: int
    spans: list[dict]


class VerdictResponse(BaseModel):
    trace_id: str
    agent_id: str
    verdict: Optional[str] = None
    timestamp: Optional[float] = None
    details: Optional[str] = None


class MarkdownReport(BaseModel):
    trace_id: str
    markdown_report: str
    sc1_result: Optional[dict] = None
    sc2_result: Optional[dict] = None
    sc3_result: Optional[dict] = None


class SilentFailureItem(BaseModel):
    trace_id: str
    agent_id: str
    status: str
    summary: str
    timestamp: float


class TopologyRiskItem(BaseModel):
    signature_id: str
    name: str
    risk_level: str
    description: str


class QuarantineRequest(BaseModel):
    agent_id: str
    reason: str
    trigger: str = "api"


class QuarantineResponse(BaseModel):
    action_id: str
    target_agent: str
    blast_radius: list[str]
    reason: str
    logged: bool
