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
    r"(\u5ba2\u6237|\u4e70\u5bb6|\u5356\u5bb6|\u4eb2|\u4f60\u597d|\u60a8\u597d|\u5728\u5417|\u4ef7\u683c|\u591a\u5c11\u94b1|"
    r"\u4e0b\u5355|\u4ed8\u6b3e|\u53d1\u8d27|\u9000\u6b3e|\u9000\u8d27|\u6362\u8d27|\u5730\u5740|\u5ba2\u670d|\u4f18\u60e0|"
    r"\u8ba2\u5355|\u7269\u6d41|\u53ef\u4ee5\u5417|\u6709\u5417|\u591a\u4e45|\u5305\u90ae|\u5e93\u5b58|\u73b0\u8d27|\u552e\u540e|"
    r"\u6295\u8bc9|\u53d1\u7968|\u5c3a\u7801|\u989c\u8272|\u914d\u9001|\u9001\u5230|\u600e\u4e48\u62cd|\u600e\u4e48\u4e0b\u5355|"
    r"hello|hi|price|order|refund|shipping|delivery|invoice|contract|payment)"
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
