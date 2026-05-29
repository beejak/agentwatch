"""
Sysmon XML event simulator for SC3 (cross-layer discrepancy).
Generates synthetic Sysmon event files for testing.

Usage:
  python agents/adversarial/sysmon_sim.py --seed    # create test files
  python agents/adversarial/sysmon_sim.py --trace <trace_id> --guid <process_guid> --extra 2
"""
import argparse
import os
import time
import uuid
from pathlib import Path

DATA_DIR = Path("data/sysmon")


def make_network_event(process_guid: str, trace_id: str, dest_ip: str) -> str:
    ts = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
    return f"""<Event>
  <System>
    <EventID>3</EventID>
    <TimeCreated SystemTime="{ts}"/>
  </System>
  <EventData>
    <Data Name="ProcessGuid">{{{process_guid}}}</Data>
    <Data Name="DestinationIp">{dest_ip}</Data>
    <Data Name="DestinationPort">443</Data>
    <Data Name="Initiated">true</Data>
    <Data Name="WatchTowerTraceId">{trace_id}</Data>
  </EventData>
</Event>"""


def seed_test_data():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    # SC3 scenario: agent reports 1 call but OS shows 3
    trace_id = "sc3-test-trace-id"
    process_guid = "sc3-test-process-guid"
    events = [
        make_network_event(process_guid, trace_id, "1.2.3.4"),
        make_network_event(process_guid, trace_id, "5.6.7.8"),    # unreported
        make_network_event(process_guid, trace_id, "9.10.11.12"),  # unreported
    ]
    out_file = DATA_DIR / "sc3_network_events.xml"
    out_file.write_text("\n".join(events))
    print(f"Seeded: {out_file} ({len(events)} events for process_guid={process_guid})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", action="store_true")
    parser.add_argument("--trace", default="test-trace")
    parser.add_argument("--guid", default=str(uuid.uuid4()))
    parser.add_argument("--extra", type=int, default=2)
    args = parser.parse_args()

    if args.seed:
        seed_test_data()
