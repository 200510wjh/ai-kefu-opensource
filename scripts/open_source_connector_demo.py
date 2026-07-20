from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


SCENARIOS = ["official_auth", "read_message", "read_lead", "customer_trial"]


def now_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def write_markdown(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Open Source Connector Demo Acceptance",
        "",
        f"Generated at: {summary['created_at']}",
        f"Connector: {summary['connector']}",
        f"Mode: {summary['mode']}",
        "",
        "## Result",
        "",
        f"- Demo status: {summary['status']}",
        f"- Scenarios covered: {', '.join(summary['scenarios'])}",
        "",
        "## Demo Evidence",
        "",
        "| Scenario | Demo Result | Evidence |",
        "| --- | --- | --- |",
    ]
    for item in summary["items"]:
        lines.append(f"| {item['scenario']} | {item['demo_result']} | {item['evidence']} |")
    lines.extend(
        [
            "",
            "## Safety Boundary",
            "",
            "- This is open-source demo evidence only.",
            "- It is useful for local development, README screenshots, CI smoke checks, and buyer demos.",
            "- It is not real-platform acceptance evidence.",
            "- Production acceptance still requires official authorization plus real read-only message and lead pulls.",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def build_summary(connector: str, output_dir: Path) -> dict[str, Any]:
    message = {
        "external_id": "demo-message-001",
        "sender_id": "demo-customer-001",
        "sender_name": "Demo Customer",
        "contact": "redacted@example.test",
        "text": "I want a product video and customer-service script for a new store launch.",
    }
    lead = {
        "external_id": "demo-lead-001",
        "name": "Demo Lead",
        "contact": "redacted-phone",
        "need": "Needs AI customer service, lead follow-up, and short-video assets.",
    }
    payloads = {
        "message_read_payload": message,
        "lead_read_payload": lead,
    }
    payload_path = output_dir / "open_source_connector_payloads.json"
    payload_path.write_text(json.dumps(payloads, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "status": "demo_ready",
        "mode": "mock_open_source",
        "connector": connector,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "scenarios": SCENARIOS,
        "payload_file": str(payload_path),
        "items": [
            {
                "scenario": "official_auth",
                "demo_result": "mocked",
                "evidence": "A demo connector identity is present; no real OAuth token is used.",
            },
            {
                "scenario": "read_message",
                "demo_result": "mocked",
                "evidence": "One sanitized demo inbound message payload is generated.",
            },
            {
                "scenario": "read_lead",
                "demo_result": "mocked",
                "evidence": "One sanitized demo lead payload is generated.",
            },
            {
                "scenario": "customer_trial",
                "demo_result": "mocked",
                "evidence": "A demo customer trial note can be used in screenshots and local CI.",
            },
        ],
    }


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="Generate safe open-source mock connector acceptance artifacts.")
    parser.add_argument("--connector", default="demo_connector")
    parser.add_argument("--output-dir", default="data/artifacts/open_source_connector_demo")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = build_summary(args.connector, output_dir)
    stamp = now_id()
    json_path = output_dir / f"open_source_connector_demo_{stamp}.json"
    md_path = output_dir / f"open_source_connector_demo_{stamp}.md"
    summary["json_report"] = str(json_path)
    summary["markdown_report"] = str(md_path)
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(md_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
