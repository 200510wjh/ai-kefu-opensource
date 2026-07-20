from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


PYTHON = Path(r"C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")


def run(cmd: list[str], cwd: Path, timeout: int = 180) -> dict[str, Any]:
    actual = cmd[:]
    if actual and actual[0] == "npm":
        npm = shutil.which("npm.cmd") or shutil.which("npm")
        if npm:
            actual[0] = npm
    completed = subprocess.run(
        actual,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout[-3000:],
        "stderr": completed.stderr[-3000:],
    }


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="Run today's AI operations local checks and build deliverables.")
    parser.add_argument("--skip-acceptance", action="store_true", help="Skip acceptance check if network is unavailable.")
    parser.add_argument("--real-platforms", action="store_true", help="Also run real desktop platform acceptance. Requires real chat windows open.")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    python = PYTHON if PYTHON.exists() else Path(sys.executable)
    report_dir = root / "运营计划" / "今日交付包"
    report_dir.mkdir(parents=True, exist_ok=True)

    checks: dict[str, Any] = {}
    checks["py_compile"] = run(
        [
            str(python),
            "-m",
            "py_compile",
            "scripts/local_demand_radar.py",
            "scripts/build_ops_delivery_pack.py",
            "scripts/today_ops_check.py",
            "scripts/desktop_auto_reply_listener.py",
            "scripts/desktop_reply_assistant.py",
            "backend/main.py",
            "backend/customer_service_saas.py",
        ],
        root,
        timeout=60,
    )
    checks["demand_scan"] = run([str(python), "scripts/local_demand_radar.py"], root, timeout=120)
    checks["ops_package"] = run([str(python), "scripts/build_ops_delivery_pack.py"], root, timeout=180)

    if not args.skip_acceptance:
        checks["acceptance_check"] = run(["npm", "run", "acceptance:check"], root, timeout=240)
    if args.real_platforms:
        checks["real_platforms"] = run(["npm", "run", "acceptance:real-platforms", "--", "--soft"], root, timeout=240)

    lines = [
        "# 今日脚本验收报告",
        "",
        f"- 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 总体：{'通过' if all(item.get('ok') for item in checks.values()) else '有未通过项'}",
        "",
    ]
    for name, item in checks.items():
        lines.extend(
            [
                f"## {name}",
                "",
                f"- 状态：{'通过' if item.get('ok') else '未通过'}",
                f"- 返回码：{item.get('returncode')}",
                "",
            ]
        )
        if item.get("stdout"):
            lines.extend(["```text", str(item["stdout"])[-1200:], "```", ""])
        if item.get("stderr"):
            lines.extend(["错误输出：", "```text", str(item["stderr"])[-1200:], "```", ""])

    report_path = report_dir / "今日脚本验收报告.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"ok": all(item.get("ok") for item in checks.values()), "report": str(report_path), "checks": checks}, ensure_ascii=False, indent=2))
    return 0 if all(item.get("ok") for item in checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
