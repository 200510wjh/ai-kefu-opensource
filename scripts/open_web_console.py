from __future__ import annotations

import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(r"C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
URL = "http://127.0.0.1:8000/script-console"


def port_open(host: str = "127.0.0.1", port: int = 8000) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        return sock.connect_ex((host, port)) == 0


def page_ready() -> bool:
    try:
        with urlopen(URL, timeout=2) as response:
            return response.status == 200
    except Exception:
        return False


def has_uvicorn(python: str) -> bool:
    try:
        completed = subprocess.run(
            [python, "-c", "import importlib.util; raise SystemExit(0 if importlib.util.find_spec('uvicorn') else 1)"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        return completed.returncode == 0
    except Exception:
        return False


def backend_python() -> str:
    candidates = []
    if PYTHON.exists():
        candidates.append(str(PYTHON))
    candidates.extend(["python", "py"])
    for candidate in candidates:
        if has_uvicorn(candidate):
            return candidate
    return str(PYTHON if PYTHON.exists() else sys.executable)


def main() -> int:
    python = backend_python()
    log_dir = ROOT / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "web_console_api.log"

    if not port_open() or not page_ready():
        with log_path.open("a", encoding="utf-8", errors="replace") as log:
            log.write("\n--- starting backend api ---\n")
            subprocess.Popen(
                [python, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000"],
                cwd=ROOT,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        for _ in range(30):
            if page_ready():
                break
            time.sleep(0.5)

    webbrowser.open(URL)
    print(f"Opened {URL}")
    print(f"Backend log: {log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
