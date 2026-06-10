"""
Tier-2 full-surface capture — kernel telemetry → host_event bridge.

eBPF collectors (Tetragon / Falco) observe the *real* network + process activity at the
syscall level — including raw sockets, DNS, and proxy-bypass connects that an HTTP proxy
cannot see, with native PID attribution. This module maps their JSON events into the
host_event schema the SC3 detector consumes ({process_guid, event_type, dst}).

Live capture requires a privileged collector (CAP_BPF/CAP_SYS_ADMIN, debugfs) on a Linux
host/microVM — see docs/REAL_TRAFFIC_VALIDATION.md. This mapping layer is unit-tested and
runs anywhere; only the *collection* needs privileges.
"""
from __future__ import annotations

from typing import Optional

_NET_FUNCS = {"tcp_connect", "tcp_v4_connect", "tcp_v6_connect", "udp_sendmsg", "connect"}


def tetragon_event_to_host_event(evt: dict) -> Optional[dict]:
    """Map a Tetragon process_kprobe/connect event → host_event, or None if not network."""
    kp = evt.get("process_kprobe") or evt.get("process_connect")
    if not kp:
        return None
    fn = kp.get("function_name", "") or evt.get("function_name", "")
    proc = kp.get("process", {}) or {}
    is_net = fn in _NET_FUNCS or "connect" in fn.lower() or bool(kp.get("destination_ip") or kp.get("socket"))
    if not is_net:
        return None
    return {
        "process_guid": proc.get("exec_id") or str(proc.get("pid", "")),
        "event_type": "NetworkConnect",
        "dst": kp.get("destination_ip") or (kp.get("socket") or {}).get("daddr"),
        "binary": proc.get("binary"),
    }


def falco_event_to_host_event(evt: dict) -> Optional[dict]:
    """Map a Falco outbound-connection alert → host_event, or None if not network."""
    fields = evt.get("output_fields", {})
    rule = (evt.get("rule") or "").lower()
    if "connect" not in rule and "outbound" not in rule and not fields.get("fd.sip"):
        return None
    return {
        "process_guid": str(fields.get("proc.pid", "")),
        "event_type": "NetworkConnect",
        "dst": fields.get("fd.sip") or fields.get("fd.rip"),
        "binary": fields.get("proc.exepath") or fields.get("proc.name"),
    }


def stream_to_host_events(lines, source: str = "tetragon") -> list[dict]:
    """Convert a stream of collector JSON lines into host_events (network only)."""
    import json
    fn = tetragon_event_to_host_event if source == "tetragon" else falco_event_to_host_event
    out = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            he = fn(json.loads(line))
        except Exception:
            continue
        if he:
            out.append(he)
    return out
