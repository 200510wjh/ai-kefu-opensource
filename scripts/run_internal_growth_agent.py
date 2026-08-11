from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.internal_growth.api import agent_run
from backend.internal_growth.models import AgentRunRequest


def load_context(args: argparse.Namespace) -> dict[str, Any]:
    if args.context_file:
        return json.loads(Path(args.context_file).read_text(encoding="utf-8"))
    if args.context_json:
        return json.loads(args.context_json)
    return {}


async def run(args: argparse.Namespace) -> int:
    task = " ".join(args.task).strip()
    if not task:
        raise SystemExit("请传入 Agent 任务，例如：根据峰会内容生成抖音和闲鱼获客草稿")
    result = await agent_run(
        AgentRunRequest(
            task=task,
            context=load_context(args),
            task_id=args.task_id,
        )
    )
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Internal Growth OS agent from the command line.")
    parser.add_argument("task", nargs="+", help="自然语言任务")
    parser.add_argument("--context-json", default="", help="JSON object context")
    parser.add_argument("--context-file", default="", help="Path to a JSON context file")
    parser.add_argument("--task-id", default=None, help="Stable task id for idempotency/audit")
    args = parser.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
