from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json(filename: str) -> Any:
    base_dir = Path(__file__).resolve().parents[1]  # .../src/analyst/
    data_dir = base_dir / "data"
    path = data_dir / filename
    return json.loads(path.read_text(encoding="utf-8"))

