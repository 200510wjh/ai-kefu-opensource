from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any


SENSITIVE_KEYS = {
    "access_token",
    "api_key",
    "authorization",
    "client_secret",
    "code",
    "cookie",
    "password",
    "refresh_token",
    "secret",
    "session_key",
    "signature",
    "token",
}


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def redact_value(key: str, value: Any) -> Any:
    lower = key.lower()
    if any(part in lower for part in SENSITIVE_KEYS):
        return "[REDACTED]"
    if isinstance(value, str) and len(value) > 160:
        return value[:120] + "...[truncated]"
    return value


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): sanitize(redact_value(str(key), item)) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize(item) for item in value[:10]]
    return value


def request_json(url: str, headers: dict[str, str], timeout: int = 45) -> tuple[int, Any]:
    request = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8", errors="replace")
        try:
            return response.status, json.loads(raw)
        except json.JSONDecodeError:
            return response.status, {"raw_text": raw[:4000]}


def post_json(url: str, payload: dict[str, Any], headers: dict[str, str] | None = None, timeout: int = 45) -> Any:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request_headers = {"Content-Type": "application/json; charset=utf-8"}
    request_headers.update(headers or {})
    request = urllib.request.Request(url, data=body, headers=request_headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def auth_headers(token: str, header_template: str) -> dict[str, str]:
    if not token:
        return {}
    if "{token}" in header_template:
        name, _, value = header_template.partition(":")
        return {name.strip(): value.strip().replace("{token}", token)}
    return {"Authorization": f"Bearer {token}"}


def extract_items(data: Any, resource: str) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if not isinstance(data, dict):
        return []
    candidates = [
        resource,
        "items",
        "data",
        "records",
        "list",
        "messages" if resource == "messages" else "leads",
    ]
    for key in candidates:
        value = data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = extract_items(value, resource)
            if nested:
                return nested
    return []


def first_text(item: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = item.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def message_payload(item: dict[str, Any], index: int) -> dict[str, Any]:
    text = first_text(item, ["text", "content", "message", "body", "last_message", "msg"])
    return {
        "external_id": first_text(item, ["external_id", "id", "message_id", "msg_id"]) or f"real-message-{index}",
        "sender_id": first_text(item, ["sender_id", "user_id", "openid", "customer_id"]) or "real-sender",
        "sender_name": first_text(item, ["sender_name", "nickname", "name"]) or "Real Customer",
        "contact": first_text(item, ["contact", "phone", "mobile", "wechat", "email"]),
        "text": text[:3000] or "Real message pulled from official read-only API.",
        "raw": sanitize(item),
    }


def lead_payload(item: dict[str, Any], index: int) -> dict[str, Any]:
    need = first_text(item, ["need", "intent", "content", "remark", "message", "source"])
    return {
        "external_id": first_text(item, ["external_id", "id", "lead_id", "customer_id"]) or f"real-lead-{index}",
        "name": first_text(item, ["name", "customer_name", "nickname"]) or "Real Lead",
        "contact": first_text(item, ["contact", "phone", "mobile", "wechat", "email"]),
        "need": need[:3000] or "Real lead pulled from official read-only API.",
        "raw": sanitize(item),
    }


def app_login(base_url: str, username: str, password: str) -> str:
    for path in ["/api/v1/auth/login", "/api/auth/login"]:
        try:
            data = post_json(base_url.rstrip("/") + path, {"username": username, "password": password})
        except Exception:
            continue
        if data.get("ok") and data.get("data", {}).get("token"):
            return str(data["data"]["token"])
        if data.get("token"):
            return str(data["token"])
    raise RuntimeError("Cannot login to app API")


def write_markdown(path: Path, result: dict[str, Any]) -> None:
    lines = [
        "# Real Connector Probe Report",
        "",
        f"Generated at: {result['created_at']}",
        f"Connector: {result['connector']}",
        f"Status: {result['status']}",
        "",
        "## Checks",
        "",
        "| Scenario | Status | Detail |",
        "| --- | --- | --- |",
    ]
    for item in result["checks"]:
        lines.append(f"| {item['scenario']} | {item['status']} | {item['detail'].replace('|', '/')} |")
    lines.extend(
        [
            "",
            "## Safety Boundary",
            "",
            "- This report stores sanitized samples only.",
            "- Secrets and credential-bearing fields are redacted.",
            "- Ingesting samples into the SaaS proves read-only import wiring, but final pass evidence still requires operator review.",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="Probe real connector read-only APIs and generate sanitized acceptance artifacts.")
    parser.add_argument("--connector", default=env("REAL_CONNECTOR_NAME", "official_connector"))
    parser.add_argument("--messages-url", default=env("REAL_CONNECTOR_MESSAGES_URL"))
    parser.add_argument("--leads-url", default=env("REAL_CONNECTOR_LEADS_URL"))
    parser.add_argument("--token", default=env("REAL_CONNECTOR_ACCESS_TOKEN"))
    parser.add_argument("--auth-header", default=env("REAL_CONNECTOR_AUTH_HEADER", "Authorization: Bearer {token}"))
    parser.add_argument("--limit", type=int, default=int(env("REAL_CONNECTOR_LIMIT", "3") or "3"))
    parser.add_argument("--output-dir", default="data/artifacts/real_connector_probe")
    parser.add_argument("--ingest", action="store_true", help="Also ingest sanitized samples into the SaaS connector read endpoints.")
    parser.add_argument("--app-base-url", default=env("APP_PUBLIC_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--app-username", default=env("APP_DEMO_USERNAME", "admin"))
    parser.add_argument("--app-password", default=env("APP_DEMO_PASSWORD", "admin123"))
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    headers = auth_headers(args.token, args.auth_header)
    checks: list[dict[str, str]] = []
    samples: dict[str, list[dict[str, Any]]] = {"messages": [], "leads": []}

    if args.token:
        checks.append({"scenario": "official_auth", "status": "configured", "detail": "Access credential is present in environment and will not be written to artifacts."})
    else:
        checks.append({"scenario": "official_auth", "status": "setup_required", "detail": "Set REAL_CONNECTOR_ACCESS_TOKEN or equivalent before probing real APIs."})

    for resource, url in [("messages", args.messages_url), ("leads", args.leads_url)]:
        scenario = "read_message" if resource == "messages" else "read_lead"
        if not url:
            checks.append({"scenario": scenario, "status": "setup_required", "detail": f"Set REAL_CONNECTOR_{resource.upper()}_URL."})
            continue
        try:
            status, data = request_json(url, headers)
            items = extract_items(data, resource)[: max(1, args.limit)]
        except Exception as exc:
            checks.append({"scenario": scenario, "status": "failed", "detail": f"Request failed: {type(exc).__name__}"})
            continue
        if not items:
            checks.append({"scenario": scenario, "status": "empty", "detail": f"HTTP request succeeded but no {resource} items were found."})
            continue
        if resource == "messages":
            samples[resource] = [message_payload(item, index + 1) for index, item in enumerate(items)]
        else:
            samples[resource] = [lead_payload(item, index + 1) for index, item in enumerate(items)]
        checks.append({"scenario": scenario, "status": "pulled", "detail": f"HTTP {status}; sanitized samples={len(samples[resource])}."})

    ingest_results: dict[str, Any] = {}
    if args.ingest:
        token = app_login(args.app_base_url, args.app_username, args.app_password)
        app_headers = {"Authorization": f"Bearer {token}"}
        for payload in samples["messages"]:
            response = post_json(args.app_base_url.rstrip("/") + f"/api/v1/connectors/{urllib.parse.quote(args.connector)}/messages/read", payload, app_headers)
            ingest_results.setdefault("messages", []).append(response)
        for payload in samples["leads"]:
            response = post_json(args.app_base_url.rstrip("/") + f"/api/v1/connectors/{urllib.parse.quote(args.connector)}/leads/read", payload, app_headers)
            ingest_results.setdefault("leads", []).append(response)

    status = "ready" if all(item["status"] in {"configured", "pulled"} for item in checks) else "setup_required"
    if any(item["status"] == "failed" for item in checks):
        status = "failed"
    result = {
        "status": status,
        "connector": args.connector,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "checks": checks,
        "samples": samples,
        "ingest": bool(args.ingest),
        "ingest_results": ingest_results,
    }
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    json_path = output_dir / f"real_connector_probe_{stamp}.json"
    md_path = output_dir / f"real_connector_probe_{stamp}.md"
    result["json_report"] = str(json_path)
    result["markdown_report"] = str(md_path)
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(md_path, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if status != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
