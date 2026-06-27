from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any


PYTHON = Path(r"C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")


def run(cmd: list[str], cwd: Path, timeout: int = 60) -> dict[str, Any]:
    completed = subprocess.run(
        cmd,
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
        "stdout": completed.stdout[-2000:],
        "stderr": completed.stderr[-2000:],
    }


def get_json(url: str, timeout: int = 20) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def post_json(url: str, payload: dict[str, Any], timeout: int = 45) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="Acceptance checks for the AI customer-service SaaS and desktop assistant.")
    parser.add_argument("--base-url", default="https://wjhai.cn/merchant-admin")
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    python = PYTHON if PYTHON.exists() else Path(sys.executable)
    checks: dict[str, Any] = {}

    checks["docs_exist"] = {
        "ok": all(
            (root / path).exists()
            for path in [
                "docs/DESKTOP_PLATFORM_ASSISTANT.md",
                "docs/HOW_TO_USE_AI_CUSTOMER_SERVICE_SYSTEM.md",
                "docs/examples/merchant_knowledge.example.txt",
                "scripts/desktop_listener.config.example.json",
            ]
        )
    }

    checks["py_compile"] = run(
        [
            str(python),
            "-m",
            "py_compile",
            "scripts/desktop_auto_reply_listener.py",
            "scripts/desktop_diagnostics.py",
            "scripts/desktop_reply_assistant.py",
            "backend/main.py",
            "backend/customer_service_saas.py",
        ],
        root,
        timeout=30,
    )

    if not args.skip_build:
        checks["frontend_build"] = run(["npm", "run", "build"], root, timeout=120)

    try:
        health = get_json(f"{args.base_url.rstrip('/')}/api/health")
        checks["online_health"] = {"ok": health.get("status") == "ok", "data": health}
    except Exception as exc:
        checks["online_health"] = {"ok": False, "error": str(exc)}

    channels: dict[str, Any] = {}
    for channel in ["wechat", "douyin_dm", "taobao", "pdd"]:
        try:
            data = post_json(
                f"{args.base_url.rstrip('/')}/api/customer-service/chat-reply-agent",
                {
                    "channel": channel,
                    "ocr_text": "客户：99元花束今天能送到吗？\n我：您好，可以帮您看。\n客户：现在下单多久到？",
                    "merchant_profile": "示例鲜花店，同城配送，99元起，2小时内尽力安排，不承诺绝对准时。",
                    "reply_goal": "回答配送并推进客户确认地址。",
                    "auto_send": False,
                },
            )
            channels[channel] = {
                "ok": bool(data.get("should_reply") and data.get("recommended_reply")),
                "reply": str(data.get("recommended_reply") or "")[:200],
            }
        except Exception as exc:
            channels[channel] = {"ok": False, "error": str(exc)}
    checks["platform_reply_api"] = {"ok": all(item.get("ok") for item in channels.values()), "channels": channels}

    diagnose = run(
        [
            str(python),
            "scripts/desktop_diagnostics.py",
            "--platform",
            "wechat",
            "--window-allowlist",
            ".*",
            "--source",
            "auto",
            "--max-chars",
            "800",
        ],
        root,
        timeout=120,
    )
    checks["desktop_diagnostics"] = diagnose

    ok = all(item.get("ok") for item in checks.values())
    print(json.dumps({"ok": ok, "checks": checks}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
