"""Unit tests for the Tier-2 kernel-telemetry → host_event bridge (no privileges needed)."""
from eval.capture.ebpf_bridge import (
    tetragon_event_to_host_event,
    falco_event_to_host_event,
    stream_to_host_events,
)


def test_tetragon_tcp_connect_maps_to_host_event():
    evt = {"process_kprobe": {
        "function_name": "tcp_connect",
        "destination_ip": "13.37.0.1",
        "process": {"exec_id": "exec-abc", "pid": 4242, "binary": "/usr/bin/python"},
    }}
    he = tetragon_event_to_host_event(evt)
    assert he is not None
    assert he["event_type"] == "NetworkConnect"
    assert he["process_guid"] == "exec-abc"   # native PID attribution
    assert he["dst"] == "13.37.0.1"


def test_tetragon_non_network_event_ignored():
    evt = {"process_exec": {"process": {"exec_id": "x", "binary": "/bin/ls"}}}
    assert tetragon_event_to_host_event(evt) is None


def test_falco_outbound_maps_to_host_event():
    evt = {"rule": "Unexpected outbound connection",
           "output_fields": {"proc.pid": 99, "fd.sip": "10.0.0.9", "proc.name": "python"}}
    he = falco_event_to_host_event(evt)
    assert he and he["event_type"] == "NetworkConnect" and he["process_guid"] == "99"


def test_stream_filters_to_network_events_only():
    import json
    lines = [
        json.dumps({"process_kprobe": {"function_name": "tcp_connect", "destination_ip": "1.2.3.4",
                                        "process": {"exec_id": "e1", "pid": 1}}}),
        json.dumps({"process_exec": {"process": {"exec_id": "e2", "pid": 2}}}),  # not network
        "",
    ]
    hes = stream_to_host_events(lines, source="tetragon")
    assert len(hes) == 1 and hes[0]["dst"] == "1.2.3.4"
