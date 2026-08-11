from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.internal_growth.workflows import run_daily_growth_workflow


def main() -> int:
    run = run_daily_growth_workflow("schedule")
    print(json.dumps(run.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0 if run.status in {"needs_human", "success"} else 1


if __name__ == "__main__":
    raise SystemExit(main())

