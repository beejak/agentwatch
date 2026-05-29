"""Gate 16: Host Telemetry — Sysmon/Falco parsing and TelemetryCorrelator."""
import uuid
import time
import pytest

from watchtower.host_telemetry.sysmon import SysmonParser, SysmonEvent
from watchtower.host_telemetry.falco import FalcoParser, FalcoEvent
from watchtower.host_telemetry.correlator import TelemetryCorrelator


SAMPLE_SYSMON_XML = """<?xml version="1.0" encoding="UTF-16"?>
<Events>
  <Event>
    <EventID>3</EventID>
    <EventData>
      <Data Name="ProcessGuid">{12345678-1234-1234-1234-123456789012}</Data>
      <Data Name="Image">C:\\agent.exe</Data>
      <Data Name="DestinationIp">1.2.3.4</Data>
      <Data Name="DestinationPort">443</Data>
    </EventData>
  </Event>
  <Event>
    <EventID>1</EventID>
    <EventData>
      <Data Name="ProcessGuid">{ABCDEF01-ABCD-ABCD-ABCD-ABCDEF012345}</Data>
      <Data Name="Image">C:\\other.exe</Data>
      <Data Name="CommandLine">python main.py</Data>
    </EventData>
  </Event>
</Events>
"""

SAMPLE_FALCO_JSON = '{"rule":"Outbound Connection","priority":"WARNING","output_fields":{"container.id":"abc123","proc.pid":1234,"fd.sip":"1.2.3.4"}}\n'


@pytest.fixture
def sysmon_parser():
    return SysmonParser()


@pytest.fixture
def falco_parser():
    return FalcoParser()


@pytest.fixture
def correlator():
    return TelemetryCorrelator()


def test_sysmon_parses_xml(sysmon_parser):
    """Sysmon XML string → list of SysmonEvent objects."""
    events = sysmon_parser.parse_string(SAMPLE_SYSMON_XML)
    assert len(events) >= 1
    assert all(isinstance(e, SysmonEvent) for e in events)


def test_sysmon_event_has_process_guid(sysmon_parser):
    events = sysmon_parser.parse_string(SAMPLE_SYSMON_XML)
    assert all(e.process_guid for e in events)


def test_sysmon_network_event_type(sysmon_parser):
    events = sysmon_parser.parse_string(SAMPLE_SYSMON_XML)
    network_events = [e for e in events if e.event_id == 3]
    assert len(network_events) >= 1
    assert network_events[0].event_type == "network_connect"


def test_falco_parses_json(falco_parser):
    event = falco_parser.parse_dict({
        "rule": "Outbound Connection",
        "priority": "WARNING",
        "output_fields": {"container.id": "abc123", "proc.pid": 1234},
    })
    assert event is not None
    assert isinstance(event, FalcoEvent)
    assert event.rule == "Outbound Connection"


async def test_correlator_register_and_resolve(correlator):
    pg = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    await correlator.register(pg, trace_id)
    resolved = await correlator.resolve(pg)
    assert resolved == trace_id


async def test_correlator_unknown_returns_none(correlator):
    resolved = await correlator.resolve("unknown-pg-xyz")
    assert resolved is None


async def test_correlator_ingest_and_get_events(correlator, sysmon_parser):
    """Events ingested via correlator appear in get_events_for_trace()."""
    pg = "{12345678-1234-1234-1234-123456789012}"
    trace_id = str(uuid.uuid4())
    await correlator.register(pg, trace_id)

    # Parse and ingest sysmon events
    events = sysmon_parser.parse_string(SAMPLE_SYSMON_XML)
    for event in events:
        await correlator.ingest_event(event)

    trace_events = await correlator.get_events_for_trace(trace_id)
    # The event with matching process_guid should be correlated
    assert len(trace_events) >= 1


async def test_sysmon_event_has_timestamp(sysmon_parser):
    events = sysmon_parser.parse_string(SAMPLE_SYSMON_XML)
    for e in events:
        assert e.timestamp > 0
