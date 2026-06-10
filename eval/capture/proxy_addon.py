"""
mitmproxy addon — the independent egress observer for Tier-1 real-traffic capture.

Every outbound request the agent makes is logged here, INDEPENDENTLY of whether the
agent emitted a Signal for it. This is the "host/network truth" the SC3 detector
compares against the agent's self-report. Each request carries X-WT-Trace / X-WT-Guid
headers so flows attribute to the right trace/process.

Run via:  mitmdump -s eval/capture/proxy_addon.py --listen-port 8081 -q
Log path: env WT_PROXY_LOG (default eval/capture/proxy_flows.jsonl)
"""
import json
import os
import time

LOG = os.environ.get("WT_PROXY_LOG", "eval/capture/proxy_flows.jsonl")


class FlowLogger:
    def request(self, flow) -> None:
        h = flow.request.headers
        rec = {
            "ts": time.time(),
            "method": flow.request.method,
            "host": flow.request.host,
            "path": flow.request.path,
            "guid": h.get("X-WT-Guid", ""),
            "trace_id": h.get("X-WT-Trace", ""),
        }
        with open(LOG, "a") as f:
            f.write(json.dumps(rec) + "\n")


addons = [FlowLogger()]
