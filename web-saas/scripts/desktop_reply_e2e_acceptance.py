from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_API_BASE = "https://wjhai.cn/merchant-admin/api"
CHANNELS = {
    "wechat": "微信",
    "douyin_dm": "抖音",
    "taobao": "淘宝/千牛",
    "pdd": "拼多多",
    "xianyu": "闲鱼",
}

CHAT_FIXTURE = """客户：99元花束今天还有吗？
客服：您好，可以帮您看一下。
客户：现在下单多久能送到？能不能保证准时？
"""

BANNED_PROMISES = ["保证准时", "一定准时", "无条件退款", "私下付款", "私下收款"]


def endpoint_url(api_base: str) -> str:
    base = api_base.rstrip("/")
    if base.endswith("/api"):
        return f"{base}/customer-service/chat-reply-agent"
    return f"{base}/api/customer-service/chat-reply-agent"


def post_json(url: str, payload: dict[str, Any], retries: int = 2) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        request = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            last_error = exc
            if attempt >= retries:
                break
            time.sleep(1 + attempt)
    raise RuntimeError(str(last_error))


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="End-to-end reply acceptance using sample chat + local knowledge + API.")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--knowledge-file", default="docs/examples/merchant_knowledge.example.txt")
    parser.add_argument("--chat-file", default="")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    knowledge = (root / args.knowledge_file).read_text(encoding="utf-8", errors="ignore")
    chat_text = (root / args.chat_file).read_text(encoding="utf-8", errors="ignore") if args.chat_file else CHAT_FIXTURE
    results: dict[str, Any] = {}

    for channel, label in CHANNELS.items():
        try:
            data = post_json(
                endpoint_url(args.api_base),
                {
                    "channel": channel,
                    "ocr_text": chat_text,
                    "merchant_profile": f"{label}桌面客服助手。\n{knowledge}",
                    "reply_goal": "回答客户问题，结合知识库，不乱承诺准时、退款或私下收款，并推进客户留下地址/用途/色系。",
                    "auto_send": False,
                },
            )
            reply = str(data.get("recommended_reply") or "")
            banned = [phrase for phrase in BANNED_PROMISES if phrase in reply]
            results[channel] = {
                "ok": bool(data.get("should_reply") and reply and not banned),
                "should_reply": bool(data.get("should_reply")),
                "reply": reply,
                "banned_promises": banned,
            }
        except Exception as exc:
            results[channel] = {"ok": False, "error": str(exc)}

    ok = all(item.get("ok") for item in results.values())
    print(json.dumps({"ok": ok, "chat_fixture": chat_text, "results": results}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
