from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from desktop_agent.adapters.base import ActiveTarget
from desktop_agent.config import AgentConfig
from desktop_agent.connectors import connector_for_platform


class MacOSAdapter:
    def capabilities(self) -> list[str]:
        return ["accessibility_window_title", "ocr", "clipboard", "paste", "send", "permission_diagnostics"]

    def run(self, args: list[str], *, input_text: str = "") -> subprocess.CompletedProcess[str]:
        return subprocess.run(args, input=input_text, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace")

    def front_window_title(self) -> str:
        script = (
            'tell application "System Events"\n'
            'set frontApp to first application process whose frontmost is true\n'
            'set appName to name of frontApp\n'
            'set winName to ""\n'
            'try\n'
            'set winName to name of front window of frontApp\n'
            'end try\n'
            'return appName & " - " & winName\n'
            'end tell'
        )
        completed = self.run(["osascript", "-e", script])
        return completed.stdout.strip() if completed.returncode == 0 else ""

    def active_target(self, config: AgentConfig) -> ActiveTarget | None:
        title = self.front_window_title()
        if not title:
            return None
        if config.window_allowlist and not any(re.search(pattern, title, re.IGNORECASE) for pattern in config.window_allowlist):
            return None
        if config.platform in {"douyin", "douyin_dm", "douyin_private_message"}:
            connector = connector_for_platform(config.platform)
            if not connector.matches_title(title, config):
                return None
            return connector.target_from_window(title, title, config)
        return ActiveTarget(window_id=title, title=title, platform=config.platform, channel=config.platform, label=config.platform)

    def read_clipboard(self) -> str:
        completed = self.run(["pbpaste"])
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or "Cannot read clipboard")
        return completed.stdout.strip()

    def read_ocr_text(self, config: AgentConfig) -> str:
        tesseract = shutil.which("tesseract")
        if not tesseract:
            raise RuntimeError("Tesseract OCR executable not found. Install Tesseract or use clipboard source.")
        screenshot_path = Path(config.debug_screenshot or "")
        if not screenshot_path:
            screenshot_path = Path(tempfile.gettempdir()) / "merchant-desktop-agent-window.png"
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        capture = self.run(["screencapture", "-x", str(screenshot_path)])
        if capture.returncode != 0:
            raise RuntimeError(capture.stderr.strip() or "Cannot capture screen. Grant Screen Recording permission.")
        output_base = str(screenshot_path.with_suffix(""))
        ocr = self.run([tesseract, str(screenshot_path), output_base, "-l", config.ocr_lang])
        if ocr.returncode != 0:
            raise RuntimeError(ocr.stderr.strip() or "OCR failed")
        text_path = Path(f"{output_base}.txt")
        return text_path.read_text(encoding="utf-8", errors="ignore").strip()[-config.max_chars :]

    def read_chat_text(self, config: AgentConfig, target: ActiveTarget) -> str:
        if config.source == "clipboard":
            return self.read_clipboard()
        if config.source in {"auto", "ocr"}:
            try:
                return self.read_ocr_text(config)
            except Exception:
                if config.source == "ocr" or not config.allow_clipboard_fallback:
                    raise
        if config.allow_clipboard_fallback:
            return self.read_clipboard()
        return ""

    def write_clipboard(self, text: str) -> None:
        completed = self.run(["pbcopy"], input_text=text)
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or "Cannot write clipboard")

    def paste_and_optionally_send(self, reply: str, send: bool, target: ActiveTarget) -> dict[str, object]:
        self.write_clipboard(reply)
        script = 'tell application "System Events" to keystroke "v" using command down'
        paste = self.run(["osascript", "-e", script])
        if paste.returncode != 0:
            return {"copied": True, "pasted": False, "sent": False, "reason": paste.stderr.strip() or "paste failed", "target_title": target.title}
        if send:
            send_result = self.run(["osascript", "-e", 'tell application "System Events" to key code 36'])
            if send_result.returncode != 0:
                return {"copied": True, "pasted": True, "sent": False, "reason": send_result.stderr.strip() or "send failed", "target_title": target.title}
        return {"copied": True, "pasted": True, "sent": bool(send), "reason": "", "target_title": target.title, "foreground_title": self.front_window_title()}


def mac_permission_diagnostics() -> dict[str, object]:
    return {
        "accessibility": "System Settings > Privacy & Security > Accessibility",
        "screen_recording": "System Settings > Privacy & Security > Screen Recording",
        "current_user": os.getenv("USER", ""),
    }
