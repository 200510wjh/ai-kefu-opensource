from __future__ import annotations

import json
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(r"C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
ACCEPTANCE = ROOT / "scripts" / "desktop_real_platform_acceptance.py"
LISTENER_LAUNCHER = ROOT / "scripts" / "desktop_listener_launcher.py"

PLATFORM_LABELS = {
    "wechat": "微信/企业微信",
    "douyin": "抖音/巨量",
    "taobao": "淘宝/千牛",
    "pdd": "拼多多",
    "xianyu": "闲鱼",
}

STATUS_LABELS = {
    "ok": "已通过：窗口里读到了真实聊天内容",
    "missing_window": "没打开：请先打开这个平台的客服聊天窗口",
    "clipboard_fallback_only": "只读到剪贴板：窗口没读到真实聊天，不算自动读取",
    "read_failed": "读取失败：找到窗口，但 UIA/OCR 没读到聊天内容",
}


class AcceptanceLauncher(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("真实平台验收器")
        self.geometry("980x700")
        self.minsize(880, 620)
        self.configure(bg="#0b1020")
        self.platforms: dict[str, tk.BooleanVar] = {
            key: tk.BooleanVar(value=True) for key in PLATFORM_LABELS
        }
        self.min_read_chars = tk.StringVar(value="80")
        self.status = tk.StringVar(value="先打开平台真实聊天窗口，再点击开始验收。")
        self.build_ui()

    def build_ui(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#0b1020")
        style.configure("Card.TFrame", background="#121a33", relief="flat")
        style.configure("TLabel", background="#0b1020", foreground="#eef3ff")
        style.configure("Card.TLabel", background="#121a33", foreground="#eef3ff")
        style.configure("TCheckbutton", background="#121a33", foreground="#eef3ff")
        style.configure("TButton", padding=8)
        style.configure("Accent.TButton", padding=10, font=("Microsoft YaHei UI", 10, "bold"))

        shell = ttk.Frame(self, padding=18)
        shell.pack(fill="both", expand=True)

        ttk.Label(shell, text="真实平台验收器", font=("Microsoft YaHei UI", 22, "bold")).pack(anchor="w")
        ttk.Label(
            shell,
            text="它会检查微信、抖音、千牛、拼多多是否真的打开了聊天页，并且 UIA/OCR 是否读到了客户消息。",
            font=("Microsoft YaHei UI", 10),
        ).pack(anchor="w", pady=(6, 14))

        body = ttk.Frame(shell)
        body.pack(fill="both", expand=True)

        left = ttk.Frame(body, style="Card.TFrame", padding=14)
        left.pack(side="left", fill="y", padx=(0, 12))
        right = ttk.Frame(body, style="Card.TFrame", padding=14)
        right.pack(side="right", fill="both", expand=True)

        ttk.Label(left, text="验收平台", style="Card.TLabel", font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w")
        for key, label in PLATFORM_LABELS.items():
            ttk.Checkbutton(left, text=label, variable=self.platforms[key]).pack(anchor="w", pady=(10, 0))

        ttk.Label(left, text="聊天内容最少字符", style="Card.TLabel").pack(anchor="w", pady=(18, 4))
        ttk.Entry(left, textvariable=self.min_read_chars, width=12).pack(anchor="w")
        ttk.Button(left, text="开始验收", style="Accent.TButton", command=self.run_acceptance).pack(fill="x", pady=(18, 8))
        ttk.Button(left, text="打开自动客服启动器", command=self.open_listener_launcher).pack(fill="x", pady=(0, 8))
        ttk.Label(left, textvariable=self.status, style="Card.TLabel", wraplength=240).pack(anchor="w", pady=(14, 0))

        ttk.Label(right, text="验收结果", style="Card.TLabel", font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w")
        self.output = tk.Text(
            right,
            bg="#050816",
            fg="#d8e6ff",
            insertbackground="#ffffff",
            wrap="word",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground="#334155",
            font=("Microsoft YaHei UI", 10),
        )
        self.output.pack(fill="both", expand=True, pady=(10, 0))
        self.write("使用步骤：\n1. 打开真实聊天窗口，不要停在登录器或平台首页。\n2. 点击开始验收。\n3. 全部通过后，再打开自动客服启动器开始监听。\n\n")

    def selected_platforms(self) -> list[str]:
        return [key for key, var in self.platforms.items() if var.get()]

    def run_acceptance(self) -> None:
        platforms = self.selected_platforms()
        if not platforms:
            self.status.set("请至少选择一个平台。")
            return
        self.status.set("正在验收，请稍等...")
        self.output.delete("1.0", tk.END)
        self.write("正在检查真实平台窗口...\n\n")
        threading.Thread(target=self._run_acceptance_thread, args=(platforms,), daemon=True).start()

    def _run_acceptance_thread(self, platforms: list[str]) -> None:
        python = PYTHON if PYTHON.exists() else Path(sys.executable)
        cmd = [
            str(python),
            str(ACCEPTANCE),
            "--soft",
            "--platforms",
            ",".join(platforms),
            "--min-read-chars",
            self.min_read_chars.get(),
        ]
        completed = subprocess.run(
            cmd,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        raw = completed.stdout.strip()
        data: dict[str, object] | None = None
        start = raw.find("{")
        if start >= 0:
            try:
                data = json.loads(raw[start:])
            except Exception:
                data = None
        self.after(0, lambda: self.render_result(data, raw, completed.stderr))

    def render_result(self, data: dict[str, object] | None, raw: str, stderr: str) -> None:
        self.output.delete("1.0", tk.END)
        if not data:
            self.status.set("验收脚本输出异常。")
            self.write(raw or stderr or "没有输出")
            return
        results = data.get("results") or {}
        if not isinstance(results, dict):
            self.status.set("验收结果格式异常。")
            self.write(json.dumps(data, ensure_ascii=False, indent=2))
            return
        strict_ok = bool(data.get("strict_ok"))
        self.status.set("全部通过，可以进入自动监听。" if strict_ok else "还有平台没通过，请看右侧处理。")
        for platform, result in results.items():
            if not isinstance(result, dict):
                continue
            label = PLATFORM_LABELS.get(str(platform), str(platform))
            status = str(result.get("status") or "unknown")
            self.write(f"【{label}】{STATUS_LABELS.get(status, status)}\n")
            if result.get("window_title"):
                self.write(f"窗口：{result.get('window_title')}\n")
            if result.get("read_mode"):
                self.write(f"读取方式：{result.get('read_mode')}\n")
            message = result.get("message")
            if message:
                self.write(f"处理：{message}\n")
            candidate = result.get("uia_chat_candidate") or result.get("ocr_chat_candidate") or result.get("clipboard_chat_candidate")
            if candidate:
                self.write(f"读到的内容片段：{candidate}\n")
            self.write("\n")
        self.write("原始 JSON：\n")
        self.write(json.dumps(data, ensure_ascii=False, indent=2))

    def open_listener_launcher(self) -> None:
        python = PYTHON if PYTHON.exists() else Path(sys.executable)
        subprocess.Popen([str(python), str(LISTENER_LAUNCHER)], cwd=ROOT)

    def write(self, text: str) -> None:
        self.output.insert(tk.END, text)
        self.output.see(tk.END)


if __name__ == "__main__":
    AcceptanceLauncher().mainloop()
