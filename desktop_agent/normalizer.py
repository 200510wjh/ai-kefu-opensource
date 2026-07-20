from __future__ import annotations

import hashlib
import re


SHELL_TEXT_PATTERNS = [
    r"^CefView$",
    r"^Chrome.*",
    r"^Google Chrome.*",
    r"^http://",
    r"^https://",
    r"^app://",
    r"^zip://",
    r"^Back$",
    r"^Forward$",
    r"^Reload$",
    r"^Close$",
    r"^Minimize$",
    r"^Maximize$",
]

CHAT_SIGNAL_PATTERN = (
    r"(客户|买家|卖家|亲|你好|您好|在吗|价格|多少钱|下单|付款|发货|退款|退货|换货|地址|客服|"
    r"优惠|订单|物流|可以吗|有吗|多久|包邮|库存|现货|售后|投诉|发票|尺码|颜色|配送|送到|怎么拍|怎么下单|"
    r"hello|hi|price|order|refund|shipping|delivery|invoice)"
)


def normalize_chat_candidate(text: str) -> str:
    useful_lines: list[str] = []
    for raw_line in text.replace("\r", "\n").splitlines():
        line = " ".join(raw_line.strip().split())
        if not line:
            continue
        if any(re.search(pattern, line, re.IGNORECASE) for pattern in SHELL_TEXT_PATTERNS):
            continue
        useful_lines.append(line)
    return "\n".join(useful_lines).strip()


def looks_like_chat_text(text: str, min_chat_chars: int = 12) -> bool:
    candidate = normalize_chat_candidate(text)
    if len(candidate) < min_chat_chars:
        return False
    return bool(re.search(CHAT_SIGNAL_PATTERN, candidate, re.IGNORECASE))


def message_hash(text: str) -> str:
    normalized = " ".join(normalize_chat_candidate(text).split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
