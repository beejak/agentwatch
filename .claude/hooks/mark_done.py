#!/usr/bin/env python3
"""Manually mark a layer as done. Usage: python mark_done.py 01"""
import sys
import re
from pathlib import Path

if len(sys.argv) < 2:
    print("Usage: python mark_done.py <layer_number>", file=sys.stderr)
    sys.exit(1)

layer_num = sys.argv[1].zfill(2)
spec_path = Path("SPEC.md")
spec = spec_path.read_text()

pattern = rf'\| {layer_num} \|([^|]+)\|([^|]+)\|([^|]+)\| TODO'
if re.search(pattern, spec):
    spec = re.sub(pattern, lambda m: m.group(0).replace("| TODO", "| DONE "), spec)
    spec_path.write_text(spec)
    print(f"Layer {layer_num} marked DONE.")
else:
    print(f"Layer {layer_num} not found or already DONE.")
