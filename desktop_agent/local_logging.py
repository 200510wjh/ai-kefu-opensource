from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def append_jsonl(path: str, item: dict[str, Any]) -> None:
    if not path:
        return
    payload = {"time": datetime.now().isoformat(timespec="seconds"), **item}
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
