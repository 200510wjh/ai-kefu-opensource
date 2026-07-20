from __future__ import annotations

import sys

from desktop_agent.config import build_parser, load_config_from_args
from desktop_agent.core import DesktopAgent


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    args = build_parser().parse_args()
    config = load_config_from_args(args)
    agent = DesktopAgent(config)
    return agent.run()


if __name__ == "__main__":
    raise SystemExit(main())
