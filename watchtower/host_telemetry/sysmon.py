"""Sysmon XML event parser — reads Windows Sysmon events from XML files."""
from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

from pydantic import BaseModel


class SysmonEvent(BaseModel):
    event_id: int           # Sysmon event ID (1=process, 3=network, 11=file)
    process_guid: str       # correlation key
    trace_id: Optional[str] = None  # populated by Correlator
    event_type: str         # "process_create","network_connect","file_create"
    details: dict = {}
    timestamp: float = 0.0

    def model_post_init(self, __context) -> None:
        if self.timestamp == 0.0:
            self.timestamp = time.time()


EVENT_TYPE_MAP = {
    1: "process_create",
    3: "network_connect",
    11: "file_create",
    5: "process_terminate",
    7: "image_load",
    10: "process_access",
}


class SysmonParser:
    """Parses Sysmon XML event files."""

    def parse_file(self, path: Path) -> list[SysmonEvent]:
        """Parse a Sysmon XML file and return list of SysmonEvents."""
        try:
            tree = ET.parse(path)
            root = tree.getroot()
            events = []
            for event_elem in root.findall(".//Event"):
                event = self._parse_event(event_elem)
                if event:
                    events.append(event)
            return events
        except Exception:
            return []

    def parse_string(self, xml_str: str) -> list[SysmonEvent]:
        """Parse Sysmon XML from a string."""
        try:
            root = ET.fromstring(xml_str)
            events = []
            # Handle single event or collection
            if root.tag == "Event":
                event = self._parse_event(root)
                if event:
                    events.append(event)
            else:
                for event_elem in root.findall(".//Event"):
                    event = self._parse_event(event_elem)
                    if event:
                        events.append(event)
            return events
        except Exception:
            return []

    def _parse_event(self, event_elem: ET.Element) -> Optional[SysmonEvent]:
        """Parse a single Sysmon Event XML element."""
        try:
            # Get EventID
            event_id_elem = event_elem.find(".//EventID")
            if event_id_elem is None:
                return None
            event_id = int(event_id_elem.text or "0")

            # Get EventData fields
            details: dict = {}
            process_guid = ""
            for data in event_elem.findall(".//Data"):
                name = data.get("Name", "")
                value = data.text or ""
                details[name] = value
                if name == "ProcessGuid":
                    process_guid = value

            if not process_guid:
                return None

            event_type = EVENT_TYPE_MAP.get(event_id, f"event_{event_id}")

            return SysmonEvent(
                event_id=event_id,
                process_guid=process_guid,
                event_type=event_type,
                details=details,
                timestamp=time.time(),
            )
        except Exception:
            return None

    def scan_directory(self, directory: Path) -> list[SysmonEvent]:
        """Scan a directory for Sysmon XML files."""
        events = []
        for xml_file in directory.glob("*.xml"):
            events.extend(self.parse_file(xml_file))
        return events
