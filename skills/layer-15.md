# SKILL: Layer 15 — FastAPI

## Job
REST API exposing Chronicle queries and Analyst results.
Langfuse scoring integration for experiments.

## Files to create
- watchtower/api/main.py
- watchtower/api/routers/traces.py
- watchtower/api/routers/analyst.py
- watchtower/api/routers/interceptor.py
- watchtower/api/schemas/responses.py

## Endpoints
GET  /api/v1/traces/{trace_id}              → full trace reconstruction
GET  /api/v1/agents/{agent_id}/verdicts     → latest verdicts
GET  /api/v1/analyst/report/{trace_id}      → full markdown report (SC1+SC2+SC3)
GET  /api/v1/analyst/silent-failures        → silent failure report (last 24h)
GET  /api/v1/analyst/topology-risks         → active signature matches
POST /api/v1/interceptor/quarantine         → trigger quarantine
GET  /api/v1/health                         → all infra status

## MarkdownReport response
```python
class MarkdownReport(BaseModel):
    trace_id:        str
    markdown_report: str    # human-readable, exportable
    sc1_result:      Optional[dict]
    sc2_result:      Optional[dict]
    sc3_result:      Optional[dict]
```

## Gate requirements (gate_15_api.py)
- /health returns 200 with infra status
- /traces/{trace_id} returns correct span count
- /analyst/report/{trace_id} returns markdown_report field populated
- /analyst/silent-failures returns list (may be empty)
- /interceptor/quarantine 422 on missing agent_id
- All endpoints return < 2s response time
