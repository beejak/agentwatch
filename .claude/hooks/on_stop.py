#!/usr/bin/env python3
"""Auto-marks layers DONE in SPEC.md when their gate test passes."""
import subprocess
import re
import sys
from pathlib import Path

spec_path = Path("SPEC.md")
if not spec_path.exists():
    sys.exit(0)

spec = spec_path.read_text()

# Check each TODO layer
for match in re.finditer(r'\| (\d+) \|([^|]+)\|([^|]+)\| gate_(\w+)\s*\| TODO', spec):
    layer_num = match.group(1).strip()
    gate_name = f"gate_{match.group(4).strip()}"

    gate_files = list(Path("tests/gates").glob(f"{gate_name}*.py")) if Path("tests/gates").exists() else []
    if not gate_files:
        continue

    gate_result = subprocess.run(
        ["python", "-m", "pytest", str(gate_files[0]), "-q", "--tb=no", "--no-header"],
        capture_output=True, text=True
    )
    if gate_result.returncode == 0:
        spec = spec.replace(
            match.group(0),
            match.group(0).replace("| TODO", "| DONE ")
        )
        print(f"[on_stop] Layer {layer_num} DONE.", file=sys.stderr)

spec_path.write_text(spec)
