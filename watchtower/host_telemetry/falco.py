"""Falco JSON event parser — reads Linux Falco security events from JSON files."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from pydantic import BaseModel


class FalcoEvent(BaseModel):
    rule: str           # Falco rule name
    priority: str       # "DEBUG","INFO","WARNING","ERROR","CRITICAL"
    process_guid: str   # derived from container_id or proc_pid
    trace_id: Optional[str] = None
    event_type: str     # "network_connect","file_write","exec","etc."
    details: dict = {}
    timestamp: float = 0.0

    def model_post_init(self, __context) -> None:
        if self.timestamp == 0.0:
            self.timestamp = time.time()


class FalcoParser:
    """Parses Falco JSON event files."""

    def parse_file(self, path: Path) -> list[FalcoEvent]:
        """Parse a Falco JSON file (newline-delimited JSON)."""
        events = []
        try:
            with path.open() as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            event = self._parse_event(data)
                            if event:
                                events.append(event)
                        except json.JSONDecodeError:
                            pass
        except Exception:
            pass
        return events

    def parse_dict(self, data: dict) -> Optional[FalcoEvent]:
        """Parse a single Falco event dict."""
        return self._parse_event(data)

    def _parse_event(self, data: dict) -> Optional[FalcoEvent]:
        """Convert Falco event dict to FalcoEvent."""
        try:
            rule = data.get("rule", "unknown")
            priority = data.get("priority", "INFO")
            output_fields = data.get("output_fields", {})

            # Derive process_guid from container_id or proc_pid
            container_id = output_fields.get("container.id", "")
            proc_pid = str(output_fields.get("proc.pid", ""))
            process_guid = container_id or proc_pid or "unknown"

            # Determine event type from rule name
            rule_lower = rule.lower()
            if "network" in rule_lower or "connect" in rule_lower:
                event_type = "network_connect"
            elif "write" in rule_lower or "file" in rule_lower:
                event_type = "file_write"
            elif "exec" in rule_lower or "spawn" in rule_lower:
                event_type = "process_exec"
            else:
                event_type = "generic"

            return FalcoEvent(
                rule=rule,
                priority=priority,
                process_guid=process_guid,
                event_type=event_type,
                details=output_fields,
                timestamp=time.time(),
            )
        except Exception:
            return None

    def scan_directory(self, directory: Path) -> list[FalcoEvent]:
        """Scan a directory for Falco JSON files."""
        events = []
        for json_file in directory.glob("*.json"):
            events.extend(self.parse_file(json_file))
        return events
