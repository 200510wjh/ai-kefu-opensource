from __future__ import annotations

import argparse
import json
import socket
import sys
import urllib.error
import urllib.request
from typing import Any


def request_json(base_url: str, path: str, payload: dict[str, Any] | None = None, timeout: float = 3) -> tuple[int, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(f"{base_url.rstrip('/')}{path}", data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else None
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = body
        return error.code, parsed
    except (urllib.error.URLError, TimeoutError, socket.timeout) as error:
        return 0, {"error": f"request failed: {error}"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Check merchant growth SaaS backend health.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=float, default=3)
    args = parser.parse_args()

    failures: list[str] = []

    checks: list[tuple[str, int, Any]] = []
    status, body = request_json(args.base_url, "/api/health", timeout=args.timeout)
    checks.append(("/api/health", status, body))
    if status == 0:
        summary = {
            "base_url": args.base_url,
            "ok": False,
            "failures": ["backend is not reachable; start the FastAPI server or use TestClient"],
            "checks": [{"path": "/api/health", "status": status, "summary": summarize_body(body)}],
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 1
    if status >= 400:
        failures.append(f"/api/health returned {status}")

    for path in ["/api/integrations/media-stack", "/api/leads"]:
        status, body = request_json(args.base_url, path, timeout=args.timeout)
        checks.append((path, status, body))
        if status >= 400:
            failures.append(f"{path} returned {status}")

    intake_payload = {
        "source": "douyin",
        "business_name": "青提茶饮万达店",
        "contact": "13800000000",
        "industry": "新式茶饮",
        "product_name": "夏日青提冰茶",
        "need_text": "想做抖音同城引流，老板发一句需求就能出短视频脚本、分镜和客服回复",
        "platform": "抖音",
        "generation_kind": "customer_service",
        "customer_message": "这个系统多少钱？能不能先看一个样例？",
        "call_to_action": "私信领取试用方案",
    }
    status, intake = request_json(args.base_url, "/api/intake/customer-need", intake_payload, timeout=args.timeout)
    checks.append(("/api/intake/customer-need", status, intake))
    if status >= 400:
        failures.append(f"/api/intake/customer-need returned {status}")
    else:
        for key in ["lead", "project", "brief", "scripts", "reply_analysis"]:
            if key not in intake:
                failures.append(f"intake response missing {key}")
        insight = intake.get("reply_analysis", {}).get("service_insight", {})
        if not insight.get("lead_score"):
            failures.append("reply_analysis.service_insight.lead_score missing")

    summary = {
        "base_url": args.base_url,
        "ok": not failures,
        "failures": failures,
        "checks": [
            {
                "path": path,
                "status": status,
                "summary": summarize_body(body),
            }
            for path, status, body in checks
        ],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if failures else 0


def summarize_body(body: Any) -> Any:
    if isinstance(body, list):
        return {"type": "list", "count": len(body)}
    if isinstance(body, dict):
        keys = list(body.keys())
        result: dict[str, Any] = {"type": "object", "keys": keys[:12]}
        if "reply_analysis" in body:
            result["reply_stage"] = body["reply_analysis"].get("service_insight", {}).get("stage")
            result["lead_score"] = body["reply_analysis"].get("service_insight", {}).get("lead_score")
        return result
    return body


if __name__ == "__main__":
    sys.exit(main())
