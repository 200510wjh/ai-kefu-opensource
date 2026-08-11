from __future__ import annotations

import re
from dataclasses import dataclass

from desktop_agent.adapters.base import ActiveTarget
from desktop_agent.config import AgentConfig
from desktop_agent.connectors.base import PreparedMessage
from desktop_agent.normalizer import normalize_chat_candidate


DOUYIN_TITLE_PATTERNS = [
    r"\u6296\u97f3",
    r"\u5de8\u91cf",
    r"\u98de\u9e3d",
    r"Douyin",
    r"TikTok",
    r"douyin\.com",
    r"jinritemai\.com",
]

UNSUPPORTED_CONTENT_PATTERNS = {
    "image": [r"\[\s*image\s*\]", r"\[\s*\u56fe\u7247\s*\]", r"\u56fe\u7247", r"\u8868\u60c5\u5305"],
    "voice": [r"\[\s*voice\s*\]", r"\[\s*\u8bed\u97f3\s*\]", r"\u8bed\u97f3"],
    "video": [r"\[\s*video\s*\]", r"\u89c6\u9891"],
    "product_card": [r"\u5546\u54c1\u5361\u7247", r"\u67e5\u770b\u5546\u54c1", r"\u5546\u54c1\u94fe\u63a5"],
}

CUSTOMER_PREFIX_RE = re.compile(
    r"^(?:\u5bf9\u65b9|\u5ba2\u6237|\u4e70\u5bb6|\u7528\u6237|\u7c89\u4e1d|\u8bbf\u5ba2|ta|TA|buyer|customer)\s*[:\uff1a-]\s*(.+)$",
    re.IGNORECASE,
)
OWN_PREFIX_RE = re.compile(
    r"^(?:\u6211|\u672c\u65b9|\u5546\u5bb6|\u5ba2\u670d|\u5df2\u53d1\u9001|me|seller|agent)\s*[:\uff1a-]\s*(.+)$",
    re.IGNORECASE,
)
CONTACT_RE = re.compile(
    r"^(?:\u8054\u7cfb\u4eba|\u5f53\u524d\u4f1a\u8bdd|\u6635\u79f0|\u5ba2\u6237|\u7c89\u4e1d|contact)\s*[:\uff1a]\s*(.+)$",
    re.IGNORECASE,
)
ACCOUNT_RE = re.compile(
    r"^(?:\u8d26\u53f7|\u4f01\u4e1a\u53f7|\u6296\u97f3\u53f7|account)\s*[:\uff1a]\s*(.+)$",
    re.IGNORECASE,
)


@dataclass
class ParsedLine:
    direction: str
    text: str


def _matches_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def _clean_lines(raw_text: str) -> list[str]:
    candidate = normalize_chat_candidate(raw_text)
    lines: list[str] = []
    for raw in candidate.replace("\r", "\n").splitlines():
        line = " ".join(raw.strip().split())
        if line:
            lines.append(line)
    return lines


def _line_text(match: re.Match[str]) -> str:
    return (match.group(1) or "").strip()


def parse_douyin_lines(raw_text: str) -> list[ParsedLine]:
    parsed: list[ParsedLine] = []
    for line in _clean_lines(raw_text):
        own = OWN_PREFIX_RE.search(line)
        if own:
            parsed.append(ParsedLine("own", _line_text(own)))
            continue
        customer = CUSTOMER_PREFIX_RE.search(line)
        if customer:
            parsed.append(ParsedLine("customer", _line_text(customer)))
            continue
        if CONTACT_RE.search(line) or ACCOUNT_RE.search(line):
            continue
        parsed.append(ParsedLine("unknown", line))
    return parsed


def unsupported_flags(text: str) -> list[str]:
    flags: list[str] = []
    for label, patterns in UNSUPPORTED_CONTENT_PATTERNS.items():
        if _matches_any(text, patterns):
            flags.append(f"unsupported_{label}")
    return flags


def extract_contact(title: str, raw_text: str) -> str:
    for line in _clean_lines(raw_text):
        match = CONTACT_RE.search(line)
        if match:
            return _line_text(match)[:80]
    parts = [item.strip() for item in re.split(r"\s+[-|]\s+| - |\|", title) if item.strip()]
    noise = re.compile(r"(\u6296\u97f3|\u79c1\u4fe1|\u5de8\u91cf|\u98de\u9e3d|Douyin|TikTok)", re.IGNORECASE)
    candidates = [part for part in parts if not noise.search(part)]
    return (candidates[0] if candidates else "")[:80]


def extract_account(title: str, raw_text: str) -> str:
    for line in _clean_lines(raw_text):
        match = ACCOUNT_RE.search(line)
        if match:
            return _line_text(match)[:80]
    account_match = re.search(r"(?:account|acct)\s*[:=]\s*([\w.@-]+)", title, re.IGNORECASE)
    return account_match.group(1)[:80] if account_match else ""


def last_customer_group(parsed: list[ParsedLine]) -> tuple[list[str], str]:
    group: list[str] = []
    last_direction = ""
    for item in reversed(parsed):
        if not item.text:
            continue
        if not last_direction:
            last_direction = item.direction
        if item.direction == "customer":
            group.insert(0, item.text)
            continue
        if item.direction == "own" and group:
            break
        if item.direction == "unknown" and not group:
            break
    return group, last_direction


class DouyinDMConnector:
    key = "douyin_dm"
    channel = "douyin_dm"

    def capabilities(self) -> list[str]:
        return [
            "douyin_dm_connector",
            "douyin_window_match",
            "douyin_contact_whitelist",
            "direction_detection",
            "self_message_guard",
            "unsupported_content_handoff",
            "message_group_merge",
        ]

    def matches_title(self, title: str, config: AgentConfig) -> bool:
        if not title:
            return False
        if config.window_allowlist and _matches_any(title, config.window_allowlist):
            return True
        return _matches_any(title, DOUYIN_TITLE_PATTERNS)

    def target_from_window(self, window_id: str, title: str, config: AgentConfig) -> ActiveTarget:
        return ActiveTarget(
            window_id=window_id,
            title=title,
            platform="douyin_dm",
            channel="douyin_dm",
            label="Douyin DM",
        )

    def prepare_message(self, raw_text: str, target: ActiveTarget, config: AgentConfig) -> PreparedMessage:
        parsed = parse_douyin_lines(raw_text)
        contact = extract_contact(target.title, raw_text)
        account = extract_account(target.title, raw_text)
        group, last_direction = last_customer_group(parsed)
        message = "\n".join(group).strip()
        raw_flags = unsupported_flags(raw_text)
        message_flags = unsupported_flags(message)
        risk_flags = [*raw_flags, *[flag for flag in message_flags if flag not in raw_flags]]
        block_reasons: list[str] = []

        if not config.authorized_account:
            block_reasons.append("authorized_account_not_configured")
        elif account and account != config.authorized_account:
            block_reasons.append("authorized_account_mismatch")
        elif not account:
            block_reasons.append("authorized_account_not_verified")

        if not config.contact_allowlist:
            block_reasons.append("contact_allowlist_not_configured")
        elif not contact or not _matches_any(contact, config.contact_allowlist):
            block_reasons.append("contact_not_whitelisted")

        if risk_flags:
            block_reasons.append("unsupported_content")
        if last_direction == "own":
            return PreparedMessage(
                should_upload=False,
                reason="last_message_from_self",
                metadata={
                    "connector": self.key,
                    "contact": contact,
                    "account": account,
                    "last_message_direction": last_direction,
                    "parse_confidence": 0.9,
                    "connector_safety": {"block_auto_send": True, "risk_flags": ["self_message"]},
                },
            )
        if not message:
            block_reasons.append("no_customer_message_group")
            message = "\n".join(item.text for item in parsed[-3:] if item.text).strip()
        if last_direction not in {"customer"}:
            block_reasons.append("unable_to_distinguish_message_direction")

        confidence = 0.9
        if not contact:
            confidence -= 0.2
        if last_direction != "customer":
            confidence -= 0.35
        if block_reasons:
            confidence -= 0.25
        confidence = max(0.05, min(0.98, confidence))
        hash_basis = f"{self.key}|{account}|{contact}|{message}"
        return PreparedMessage(
            should_upload=bool(message),
            message_text=message,
            hash_basis=hash_basis,
            metadata={
                "connector": self.key,
                "contact": contact,
                "account": account,
                "last_message_direction": last_direction,
                "merged_message_count": len(group),
                "parse_confidence": round(confidence, 2),
                "connector_safety": {
                    "block_auto_send": bool(block_reasons),
                    "block_reasons": block_reasons,
                    "risk_flags": list(dict.fromkeys([*risk_flags, *block_reasons])),
                },
            },
            reason="; ".join(block_reasons),
        )
