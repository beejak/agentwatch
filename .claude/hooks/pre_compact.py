#!/usr/bin/env python3
"""Runs before context compaction. Saves current layer state to PROGRESS.md."""
import re
import sys
from pathlib import Path
from datetime import datetime

spec = Path("SPEC.md").read_text()
done  = len(re.findall(r'\| DONE ', spec))
total = len(re.findall(r'\| (TODO|DONE) ', spec))
next_todo = re.search(r'\| (\d+) \|[^|]+\|[^|]+\|[^|]+\| TODO', spec)
next_layer = next_todo.group(1).strip() if next_todo else "complete"

progress = Path("PROGRESS.md")
current = progress.read_text() if progress.exists() else ""

checkpoint_line = f"\n## Last Checkpoint\n{datetime.now().isoformat()}\nDone: {done}/{total}\nNext layer: {next_layer}\nResume: make gate-all then continue from SPEC.md §T\n"

# Append checkpoint to PROGRESS.md
progress.write_text(current + checkpoint_line)
print(f"[pre_compact] Saved. Done={done}/{total}. Next={next_layer}.", file=sys.stderr)
