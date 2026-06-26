from __future__ import annotations

import re
from pathlib import Path


SKIP_DIRS = {".git", "node_modules", "dist", "data", "__pycache__", ".venv", "external", "videos"}
PLACEHOLDERS = ("your_", "example", "placeholder", "changeme", "xxx", "sk-xxxxxxxx")
PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?i)(api[_-]?key|secret|token|password)[ \t]*[:=][ \t]*['\"]?[A-Za-z0-9_\-]{12,}"),
    re.compile(r"(?i)(access[_-]?key|client[_-]?secret)[ \t]*[:=][ \t]*['\"]?[A-Za-z0-9_\-]{12,}"),
]


def iter_files(root: Path):
    for path in root.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.is_file():
            yield path


def main() -> int:
    findings: list[str] = []
    for path in iter_files(Path.cwd()):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in PATTERNS:
            for match in pattern.finditer(text):
                matched = match.group(0).lower()
                if any(token in matched for token in PLACEHOLDERS):
                    continue
                findings.append(f"{path}:{text.count(chr(10), 0, match.start()) + 1}: {match.group(0)[:48]}...")
    if findings:
        print("Potential secrets found:")
        print("\n".join(findings))
        return 1
    print("No obvious secrets found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
