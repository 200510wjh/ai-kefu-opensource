from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


PYTHON = Path(r"C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")


def run(cmd: list[str], cwd: Path, timeout: int = 60) -> dict[str, Any]:
    if cmd and cmd[0].lower() == "npm":
        npm = shutil.which("npm.cmd") or shutil.which("npm")
        if npm:
            cmd = [npm, *cmd[1:]]
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


def request_json(url: str, method: str = "GET", payload: dict[str, Any] | None = None, headers: dict[str, str] | None = None, timeout: int = 45, retries: int = 2) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    request_headers = {"Content-Type": "application/json; charset=utf-8"}
    request_headers.update(headers or {})
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            last_error = exc
            if attempt >= retries:
                break
            time.sleep(1 + attempt)
    raise RuntimeError(str(last_error))


def get_json(url: str, headers: dict[str, str] | None = None, timeout: int = 20) -> dict[str, Any]:
    return request_json(url, headers=headers, timeout=timeout)


def post_json(url: str, payload: dict[str, Any], timeout: int = 45) -> dict[str, Any]:
    return request_json(url, method="POST", payload=payload, timeout=timeout)


def post_json_auth(url: str, payload: dict[str, Any], token: str, timeout: int = 45) -> dict[str, Any]:
    return request_json(url, method="POST", payload=payload, headers={"Authorization": f"Bearer {token}"}, timeout=timeout)


def get_json_auth(url: str, token: str, timeout: int = 45) -> Any:
    return request_json(url, headers={"Authorization": f"Bearer {token}"}, timeout=timeout)


def login(base_url: str) -> dict[str, Any]:
    last_error = ""
    for username in ["ai_kefu_demo", "admin"]:
        try:
            data = post_json(f"{base_url.rstrip('/')}/api/auth/login", {"username": username, "password": "admin123"})
            if data.get("token"):
                return data
        except Exception as exc:
            last_error = str(exc)
    raise RuntimeError(f"Cannot login with demo credentials: {last_error}")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="Acceptance checks for the AI customer-service SaaS and desktop assistant.")
    parser.add_argument("--base-url", default="https://wjhai.cn/merchant-admin")
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--require-real-platforms", action="store_true", help="Also require real WeChat/Douyin/Taobao/PDD/Xianyu windows to be open and readable.")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    python = PYTHON if PYTHON.exists() else Path(sys.executable)
    checks: dict[str, Any] = {}

    checks["docs_exist"] = {
        "ok": all(
            (root / path).exists()
            for path in [
                "先看这个-怎么使用AI客服.md",
                "docs/ACCEPTANCE_MATRIX.md",
                "docs/DESKTOP_PLATFORM_ASSISTANT.md",
                "docs/HOW_TO_USE_AI_CUSTOMER_SERVICE_SYSTEM.md",
                "docs/examples/merchant_knowledge.example.txt",
                "自动准备客服平台.bat",
                "启动AI自动客服.bat",
                "验收真实平台.bat",
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
            "scripts/desktop_acceptance_launcher.py",
            "scripts/desktop_listener_launcher.py",
            "scripts/desktop_platform_prepare.py",
            "scripts/desktop_real_platform_acceptance.py",
            "scripts/desktop_reply_e2e_acceptance.py",
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
    for channel in ["wechat", "douyin_dm", "taobao", "pdd", "xianyu"]:
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

    checks["reply_e2e"] = run(
        [
            str(python),
            "scripts/desktop_reply_e2e_acceptance.py",
        ],
        root,
        timeout=120,
    )

    try:
        auth = login(args.base_url)
        token = str(auth["token"])
        merchant = auth.get("merchant", {})
        merchant_code = str(merchant.get("merchant_code") or "WJDEMO001")
        stamp = int(time.time())
        imported = post_json_auth(
            f"{args.base_url.rstrip('/')}/api/knowledge/import",
            {
                "title": f"acceptance-{stamp}",
                "source_type": "faq",
                "tags": "acceptance,desktop",
                "content": "Q: 今天能送到吗？\nA: 同城配送一般 2 小时内尽力安排，但不承诺绝对准时。\nQ: 99 元花束还有吗？\nA: 可以先发地址、用途和色系，客服确认库存后安排。",
                "sync_to_faq": True,
            },
            token,
        )
        knowledge = get_json_auth(f"{args.base_url.rstrip('/')}/api/knowledge", token)
        session = post_json(
            f"{args.base_url.rstrip('/')}/api/widget/session",
            {"merchant_code": merchant_code, "visitor_id": f"acceptance-{stamp}", "page_url": "acceptance://local", "user_agent": "acceptance-check"},
        )
        message = post_json(
            f"{args.base_url.rstrip('/')}/api/widget/message",
            {
                "merchant_code": merchant_code,
                "session_id": session["session_id"],
                "visitor_id": f"acceptance-{stamp}",
                "message": "99元花束今天能送到吗？",
                "page_url": "acceptance://local",
            },
        )
        conversations = get_json_auth(f"{args.base_url.rstrip('/')}/api/conversations", token)
        checks["saas_core_flow"] = {
            "ok": bool(
                token
                and merchant_code
                and imported.get("imported", 0) >= 1
                and isinstance(knowledge, list)
                and session.get("session_id")
                and message.get("ai_reply")
                and any(item.get("session_id") == session.get("session_id") for item in conversations)
            ),
            "merchant_code": merchant_code,
            "knowledge_imported": imported.get("imported"),
            "knowledge_count": len(knowledge) if isinstance(knowledge, list) else None,
            "widget_session": session.get("session_id"),
            "widget_reply": str(message.get("ai_reply") or "")[:200],
            "conversation_found": any(item.get("session_id") == session.get("session_id") for item in conversations) if isinstance(conversations, list) else False,
        }
    except Exception as exc:
        checks["saas_core_flow"] = {"ok": False, "error": str(exc)}

    try:
        sys.path.insert(0, str(root / "scripts"))
        import desktop_auto_reply_listener as desktop_listener  # type: ignore

        history_path = root / "data" / "desktop-listener" / "acceptance-history.jsonl"
        if history_path.exists():
            history_path.unlink()
        desktop_listener.append_history(
            str(history_path),
            {
                "platform": "wechat",
                "pending": ["客户：99元花束还有吗？"],
                "reply": "可以先发地址和色系，我帮您确认库存。",
            },
        )
        rows = desktop_listener.load_history(str(history_path), 3)
        target = desktop_listener.ActiveTarget(
            hwnd=0,
            title="验收窗口",
            platform="wechat",
            backend_channel="wechat",
            label="微信",
        )
        config = desktop_listener.ListenerConfig(
            api_base=args.base_url,
            platform="wechat",
            source="clipboard",
            merchant_profile="验收商家",
            knowledge_file="",
            reply_goal="验收历史上下文",
            target_title="",
            window_allowlist=[],
            poll_seconds=1,
            min_send_gap_seconds=20,
            once=True,
            paste=False,
            auto_send=False,
            dry_run=True,
            max_chars=2000,
            min_text_chars=30,
            min_chat_chars=12,
            allow_non_chat_text=False,
            allow_clipboard_fallback=False,
            ocr_lang="chi_sim+eng",
            debug_screenshot="",
            history_file=str(history_path),
            history_limit=3,
        )
        payload_with_history = desktop_listener.build_chat_payload(config, target, "客户：那今天能送到吗？")
        checks["desktop_history"] = {
            "ok": bool(rows and rows[-1].get("reply")),
            "history_file": str(history_path),
            "rows": len(rows),
        }
        checks["desktop_history_context"] = {
            "ok": (
                "Previous desktop assistant context:" in payload_with_history
                and "客户：99元花束还有吗？" in payload_with_history
                and "可以先发地址和色系" in payload_with_history
                and "客户：那今天能送到吗？" in payload_with_history
            ),
            "sample": payload_with_history[:500],
        }
        checks["chat_text_filter"] = {
            "ok": (
                not desktop_listener.looks_like_chat_text("微信多开\nCefView\nzip://example\n系统\n还原\n最大化\n关闭")
                and not desktop_listener.looks_like_chat_text(
                    "淘宝 - Google Chrome\n地址和搜索栏\ntaobao.com\nAI客服助手 可以访问此网站\n"
                    "扩展程序\n书签\n标签页搜索\n扣子 - 技能商店 - 内存用量 - 293 MB"
                )
                and not desktop_listener.looks_like_chat_text(
                    "抖音\n抖音精选电脑版 - 抖音旗下优质视频平台\n全部\n公开课\n游戏\n影视\n"
                    "音乐\n二次元\n知识\n体育\n美食\n汽车\n小剧场\n生活vlog\n旅行\n三农\n动物\n亲子\n美妆穿搭"
                )
                and not desktop_listener.looks_like_chat_text(
                    "女装Ai带货，别再盯着同行抄了\n全网最详细带工厂老板拍获客短视频开头 视频很长"
                )
                and desktop_listener.looks_like_chat_text("客户：99元花束还有吗？现在下单多久能送到？")
            ),
            "shell_candidate": desktop_listener.normalize_chat_candidate("微信多开\nCefView\nzip://example\n系统\n还原\n最大化\n关闭"),
            "browser_shell_candidate": desktop_listener.normalize_chat_candidate(
                "淘宝 - Google Chrome\n地址和搜索栏\ntaobao.com\nAI客服助手 可以访问此网站\n"
                "扩展程序\n书签\n标签页搜索\n扣子 - 技能商店 - 内存用量 - 293 MB"
            ),
            "douyin_home_candidate": desktop_listener.normalize_chat_candidate(
                "抖音\n抖音精选电脑版 - 抖音旗下优质视频平台\n全部\n公开课\n游戏\n影视\n"
                "音乐\n二次元\n知识\n体育\n美食\n汽车\n小剧场\n生活vlog\n旅行\n三农\n动物\n亲子\n美妆穿搭"
            ),
            "chat_candidate": desktop_listener.normalize_chat_candidate("客户：99元花束还有吗？现在下单多久能送到？"),
        }
        original_write_clipboard = desktop_listener.write_clipboard
        original_focus_window = desktop_listener.focus_window
        original_press_vk = desktop_listener.press_vk
        original_window_title = desktop_listener.window_title
        original_foreground_window_title = desktop_listener.foreground_window_title
        captured: dict[str, Any] = {"clipboard": "", "keys": []}
        try:
            desktop_listener.write_clipboard = lambda text: captured.update({"clipboard": text})  # type: ignore[assignment]
            desktop_listener.focus_window = lambda hwnd: False  # type: ignore[assignment]
            desktop_listener.press_vk = lambda vk, up=False: captured["keys"].append((vk, up))  # type: ignore[assignment]
            desktop_listener.window_title = lambda hwnd: "验收目标窗口"  # type: ignore[assignment]
            desktop_listener.foreground_window_title = lambda: "错误前台窗口"  # type: ignore[assignment]
            paste_result = desktop_listener.paste_and_optionally_send("验收回复", send=True, hwnd=12345)
            checks["paste_focus_guard"] = {
                "ok": (
                    captured["clipboard"] == "验收回复"
                    and captured["keys"] == []
                    and paste_result.get("pasted") is False
                    and paste_result.get("sent") is False
                    and paste_result.get("reason") == "target_window_not_focused"
                ),
                "result": paste_result,
                "captured": captured,
            }
        finally:
            desktop_listener.write_clipboard = original_write_clipboard
            desktop_listener.focus_window = original_focus_window
            desktop_listener.press_vk = original_press_vk
            desktop_listener.window_title = original_window_title
            desktop_listener.foreground_window_title = original_foreground_window_title
    except Exception as exc:
        checks["desktop_history"] = {"ok": False, "error": str(exc)}
        checks["desktop_history_context"] = {"ok": False, "error": str(exc)}
        checks["chat_text_filter"] = {"ok": False, "error": str(exc)}
        checks["paste_focus_guard"] = {"ok": False, "error": str(exc)}

    try:
        import desktop_listener_launcher as launcher  # type: ignore

        expected_platforms = {
            "微信": "wechat",
            "WeChat": "wechat",
            "千牛工作台": "taobao",
            "拼多多商家后台": "pdd",
            "闲鱼消息": "xianyu",
            "咸鱼聊天": "xianyu",
            "普通浏览器窗口": "",
        }
        actual_platforms = {title: launcher.guess_platform(title) for title in expected_platforms}
        checks["launcher_platform_guess"] = {
            "ok": actual_platforms == expected_platforms,
            "expected": expected_platforms,
            "actual": actual_platforms,
        }
    except Exception as exc:
        checks["launcher_platform_guess"] = {"ok": False, "error": str(exc)}

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
            "--allow-clipboard-fallback",
            "--max-chars",
            "800",
        ],
        root,
        timeout=120,
    )
    diagnostics_stdout = str(diagnose.get("stdout") or "")
    diagnostics_reported = '"checks"' in diagnostics_stdout and '"visible_platform_windows"' in diagnostics_stdout
    checks["desktop_diagnostics"] = {
        **diagnose,
        "ok": diagnostics_reported,
        "reported": diagnostics_reported,
        "note": "Basic acceptance only requires diagnostics to run and report. Use npm run acceptance:real-platforms to require real customer chat windows.",
    }

    prepare_report = root / "data" / "desktop-listener" / "platform-prepare-report.md"
    if prepare_report.exists():
        prepare_report.unlink()
    prepare = run(
        [
            str(python),
            "scripts/desktop_platform_prepare.py",
            "--soft",
            "--wait-seconds",
            "0",
            "--report",
            str(prepare_report),
        ],
        root,
        timeout=60,
    )
    checks["desktop_platform_prepare"] = {
        **prepare,
        "ok": bool(prepare.get("ok") and prepare_report.exists()),
        "report_exists": prepare_report.exists(),
        "report": str(prepare_report),
    }

    if args.require_real_platforms:
        checks["real_platform_windows"] = run(
            [
                str(python),
                "scripts/desktop_real_platform_acceptance.py",
            ],
            root,
            timeout=240,
        )

    ok = all(item.get("ok") for item in checks.values())
    print(json.dumps({"ok": ok, "checks": checks}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
