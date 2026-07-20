from __future__ import annotations

import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from desktop_auto_reply_listener import CONFIRM_AUTO_SEND, PLATFORMS, enum_visible_windows


ROOT = Path(__file__).resolve().parents[1]
LISTENER = ROOT / "scripts" / "desktop_auto_reply_listener.py"
DEFAULT_KNOWLEDGE = ROOT / "docs" / "examples" / "merchant_knowledge.example.txt"
DEFAULT_HISTORY = ROOT / "data" / "desktop-listener" / "history.jsonl"
DEFAULT_SCREENSHOT = ROOT / "data" / "desktop-listener" / "latest-window.png"


def guess_platform(title: str) -> str:
    platform_order = ["wechat_work", *[name for name in PLATFORMS if name != "wechat_work"]]
    for platform in platform_order:
        info = PLATFORMS[platform]
        if platform == "douyin_dm":
            continue
        for pattern in info["allowlist"]:
            if re.search(str(pattern), title, re.IGNORECASE):
                return platform
    return ""


class DesktopListenerLauncher(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("AI 自动客服监听器")
        self.geometry("980x680")
        self.minsize(880, 620)
        self.process: subprocess.Popen[str] | None = None
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.windows: list[tuple[int, str]] = []

        self.platform = tk.StringVar(value="wechat")
        self.source = tk.StringVar(value="auto")
        self.selected_title = tk.StringVar(value="")
        self.knowledge_file = tk.StringVar(value=str(DEFAULT_KNOWLEDGE))
        self.poll_seconds = tk.StringVar(value="2")
        self.min_send_gap = tk.StringVar(value="20")
        self.paste_enabled = tk.BooleanVar(value=True)
        self.send_enabled = tk.BooleanVar(value=False)
        self.dry_run = tk.BooleanVar(value=False)
        self.clipboard_fallback = tk.BooleanVar(value=False)
        self.status_text = tk.StringVar(value="先打开微信/企业微信/抖音/千牛/拼多多/闲鱼客服窗口，再点刷新窗口。")

        self.configure(bg="#0b1020")
        self.build_ui()
        self.refresh_windows()
        self.after(200, self.drain_logs)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def build_ui(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#0b1020")
        style.configure("Card.TFrame", background="#121a33", relief="flat")
        style.configure("TLabel", background="#0b1020", foreground="#eef3ff")
        style.configure("Card.TLabel", background="#121a33", foreground="#eef3ff")
        style.configure("TButton", padding=8)
        style.configure("Accent.TButton", padding=10, font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("TCheckbutton", background="#121a33", foreground="#eef3ff")
        style.configure("TCombobox", fieldbackground="#ffffff")

        shell = ttk.Frame(self, padding=18)
        shell.pack(fill="both", expand=True)

        header = ttk.Frame(shell)
        header.pack(fill="x", pady=(0, 14))
        ttk.Label(header, text="AI 自动客服监听器", font=("Microsoft YaHei UI", 22, "bold")).pack(anchor="w")
        ttk.Label(
            header,
            text="不用复制命令。选择真实客服窗口后开始监听，系统会自动读消息、调用后台 AI、把回复粘贴到聊天输入框。",
            font=("Microsoft YaHei UI", 10),
        ).pack(anchor="w", pady=(6, 0))

        main = ttk.Frame(shell)
        main.pack(fill="both", expand=True)

        left = ttk.Frame(main, style="Card.TFrame", padding=14)
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))

        right = ttk.Frame(main, style="Card.TFrame", padding=14)
        right.pack(side="right", fill="both", expand=True)

        ttk.Label(left, text="1. 选择要监听的窗口", style="Card.TLabel", font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w")
        window_bar = ttk.Frame(left, style="Card.TFrame")
        window_bar.pack(fill="x", pady=(10, 8))
        ttk.Button(window_bar, text="刷新窗口", command=self.refresh_windows).pack(side="left")
        ttk.Label(window_bar, textvariable=self.status_text, style="Card.TLabel").pack(side="left", padx=12)

        self.window_list = tk.Listbox(
            left,
            height=14,
            bg="#0f172a",
            fg="#eef3ff",
            selectbackground="#7c3aed",
            selectforeground="#ffffff",
            activestyle="none",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground="#334155",
            font=("Microsoft YaHei UI", 10),
        )
        self.window_list.pack(fill="both", expand=True)
        self.window_list.bind("<<ListboxSelect>>", self.on_window_selected)

        form = ttk.Frame(left, style="Card.TFrame")
        form.pack(fill="x", pady=(14, 0))
        self.add_combo(form, "平台", self.platform, [("wechat", "微信"), ("wechat_work", "企业微信"), ("douyin", "抖音/巨量"), ("taobao", "淘宝/千牛"), ("pdd", "拼多多"), ("xianyu", "闲鱼")], 0)
        self.add_combo(form, "读取方式", self.source, [("auto", "自动(UIA+OCR)"), ("uia", "窗口文本"), ("ocr", "截图识别"), ("clipboard", "剪贴板")], 1)

        ttk.Label(form, text="知识库文件", style="Card.TLabel").grid(row=2, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(form, textvariable=self.knowledge_file).grid(row=2, column=1, sticky="ew", pady=(10, 0), padx=(8, 8))
        ttk.Button(form, text="选择", command=self.pick_knowledge).grid(row=2, column=2, pady=(10, 0))

        ttk.Label(form, text="监听间隔(秒)", style="Card.TLabel").grid(row=3, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(form, textvariable=self.poll_seconds, width=12).grid(row=3, column=1, sticky="w", pady=(10, 0), padx=(8, 0))
        ttk.Label(form, text="自动发送间隔(秒)", style="Card.TLabel").grid(row=4, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(form, textvariable=self.min_send_gap, width=12).grid(row=4, column=1, sticky="w", pady=(10, 0), padx=(8, 0))
        form.columnconfigure(1, weight=1)

        options = ttk.Frame(left, style="Card.TFrame")
        options.pack(fill="x", pady=(12, 0))
        ttk.Checkbutton(options, text="生成后自动粘贴到输入框", variable=self.paste_enabled).pack(anchor="w")
        ttk.Checkbutton(options, text="自动按 Enter 发送", variable=self.send_enabled).pack(anchor="w", pady=(6, 0))
        ttk.Checkbutton(options, text="允许剪贴板兜底（只适合排查，不算真正自动读取）", variable=self.clipboard_fallback).pack(anchor="w", pady=(6, 0))
        ttk.Checkbutton(options, text="只测试，不粘贴不发送", variable=self.dry_run).pack(anchor="w", pady=(6, 0))

        actions = ttk.Frame(left, style="Card.TFrame")
        actions.pack(fill="x", pady=(16, 0))
        ttk.Button(actions, text="开始自动监听", style="Accent.TButton", command=self.start_listener).pack(side="left")
        ttk.Button(actions, text="停止", command=self.stop_listener).pack(side="left", padx=10)

        ttk.Label(right, text="运行日志", style="Card.TLabel", font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w")
        self.log_box = tk.Text(
            right,
            bg="#050816",
            fg="#d8e6ff",
            insertbackground="#ffffff",
            wrap="word",
            height=24,
            borderwidth=0,
            highlightthickness=1,
            highlightbackground="#334155",
            font=("Consolas", 10),
        )
        self.log_box.pack(fill="both", expand=True, pady=(10, 0))
        self.write_log("提示：自动发送会真的按 Enter。前期建议先只开“自动粘贴”，确认回复没问题后再开启自动发送。\n")

    def add_combo(self, parent: ttk.Frame, label: str, var: tk.StringVar, values: list[tuple[str, str]], row: int) -> None:
        ttk.Label(parent, text=label, style="Card.TLabel").grid(row=row, column=0, sticky="w", pady=(10, 0))
        combo = ttk.Combobox(parent, textvariable=var, values=[key for key, _ in values], state="readonly", width=18)
        combo.grid(row=row, column=1, sticky="w", pady=(10, 0), padx=(8, 0))
        ttk.Label(parent, text=" / ".join(f"{key}={text}" for key, text in values), style="Card.TLabel").grid(
            row=row, column=2, sticky="w", pady=(10, 0), padx=(10, 0)
        )

    def refresh_windows(self) -> None:
        self.windows = [(hwnd, title) for hwnd, title in enum_visible_windows() if title.strip()]
        self.window_list.delete(0, tk.END)
        for _, title in self.windows:
            marker = "  ★" if guess_platform(title) else ""
            self.window_list.insert(tk.END, title + marker)
        self.status_text.set(f"已找到 {len(self.windows)} 个可见窗口")

    def on_window_selected(self, _event: object | None = None) -> None:
        selection = self.window_list.curselection()
        if not selection:
            return
        _, title = self.windows[selection[0]]
        self.selected_title.set(title)
        detected_platform = guess_platform(title)
        if detected_platform:
            self.platform.set(detected_platform)
        self.write_log(f"已选择窗口：{title}\n")

    def pick_knowledge(self) -> None:
        filename = filedialog.askopenfilename(
            title="选择知识库文件",
            filetypes=[("知识库文件", "*.txt *.md *.json *.csv"), ("所有文件", "*.*")],
            initialdir=str(ROOT),
        )
        if filename:
            self.knowledge_file.set(filename)

    def build_command(self) -> list[str]:
        title = self.selected_title.get().strip()
        if not title:
            raise ValueError("请先在左侧选择一个真实客服窗口。")
        escaped_title = re.escape(title.replace("  ★", ""))
        command = [
            sys.executable,
            str(LISTENER),
            "--platform",
            self.platform.get(),
            "--source",
            self.source.get(),
            "--target-title",
            escaped_title,
            "--window-allowlist",
            escaped_title,
            "--knowledge-file",
            self.knowledge_file.get(),
            "--poll-seconds",
            self.poll_seconds.get(),
            "--min-send-gap-seconds",
            self.min_send_gap.get(),
            "--debug-screenshot",
            str(DEFAULT_SCREENSHOT),
            "--history-file",
            str(DEFAULT_HISTORY),
        ]
        if self.paste_enabled.get():
            command.append("--paste")
        if self.clipboard_fallback.get():
            command.append("--allow-clipboard-fallback")
        if self.dry_run.get():
            command.append("--dry-run")
        if self.send_enabled.get():
            command.extend(["--send", "--confirm-send", CONFIRM_AUTO_SEND])
        return command

    def start_listener(self) -> None:
        if self.process and self.process.poll() is None:
            messagebox.showinfo("正在监听", "监听器已经在运行。")
            return
        if self.send_enabled.get():
            ok = messagebox.askyesno("确认自动发送", "开启后会自动按 Enter 发送回复。确认只用于你自己的客服窗口吗？")
            if not ok:
                return
        try:
            command = self.build_command()
        except ValueError as exc:
            messagebox.showwarning("缺少窗口", str(exc))
            return

        DEFAULT_HISTORY.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_SCREENSHOT.parent.mkdir(parents=True, exist_ok=True)
        self.write_log("\n监听启动中...\n")
        self.process = subprocess.Popen(
            command,
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP") else 0,
        )
        threading.Thread(target=self.read_process_logs, daemon=True).start()

    def read_process_logs(self) -> None:
        if not self.process or not self.process.stdout:
            return
        for line in self.process.stdout:
            self.log_queue.put(line)
        code = self.process.poll()
        self.log_queue.put(f"\n监听器已退出，退出码：{code}\n")

    def stop_listener(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.write_log("\n已请求停止监听器。\n")
        else:
            self.write_log("\n当前没有运行中的监听器。\n")

    def write_log(self, text: str) -> None:
        self.log_box.insert(tk.END, text)
        self.log_box.see(tk.END)

    def drain_logs(self) -> None:
        try:
            while True:
                self.write_log(self.log_queue.get_nowait())
        except queue.Empty:
            pass
        self.after(200, self.drain_logs)

    def on_close(self) -> None:
        self.stop_listener()
        self.destroy()


if __name__ == "__main__":
    DesktopListenerLauncher().mainloop()
