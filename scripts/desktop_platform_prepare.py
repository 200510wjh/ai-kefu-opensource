from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from desktop_auto_reply_listener import PLATFORMS, enum_visible_windows


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "data" / "desktop-listener" / "platform-prepare-report.md"
DEFAULT_PLATFORMS = ["wechat", "wechat_work", "douyin", "taobao", "pdd", "xianyu"]


@dataclass(frozen=True)
class PlatformHints:
    label: str
    keywords: tuple[str, ...]
    common_paths: tuple[str, ...]


PLATFORM_HINTS: dict[str, PlatformHints] = {
    "wechat": PlatformHints(
        label="微信",
        keywords=("微信", "WeChat"),
        common_paths=(
            r"C:\Program Files\Tencent\WeChat\WeChat.exe",
            r"C:\Program Files (x86)\Tencent\WeChat\WeChat.exe",
            r"%LOCALAPPDATA%\Tencent\WeChat\WeChat.exe",
        ),
    ),
    "wechat_work": PlatformHints(
        label="企业微信",
        keywords=("企业微信", "WXWork", "WeCom", "WeChat Work"),
        common_paths=(
            r"C:\Program Files\WXWork\WXWork.exe",
            r"C:\Program Files (x86)\WXWork\WXWork.exe",
        ),
    ),
    "douyin": PlatformHints(
        label="抖音/巨量",
        keywords=("抖音", "Douyin", "巨量", "Jinritemai", "Bytedance"),
        common_paths=(
            r"C:\Program Files\Douyin\Douyin.exe",
            r"C:\Program Files (x86)\Douyin\Douyin.exe",
            r"%LOCALAPPDATA%\Programs\Douyin\Douyin.exe",
        ),
    ),
    "taobao": PlatformHints(
        label="淘宝/千牛",
        keywords=("千牛", "淘宝", "旺旺", "Qianniu", "AliWorkbench", "WangWang"),
        common_paths=(
            r"C:\Program Files (x86)\AliWorkbench\AliWorkbench.exe",
            r"C:\Program Files\AliWorkbench\AliWorkbench.exe",
            r"C:\Program Files (x86)\千牛\AliWorkbench.exe",
            r"C:\Program Files\千牛\AliWorkbench.exe",
        ),
    ),
    "pdd": PlatformHints(
        label="拼多多",
        keywords=("拼多多", "PDD", "商家后台", "Pinduoduo"),
        common_paths=(
            r"C:\Program Files\Pinduoduo\Pinduoduo.exe",
            r"C:\Program Files (x86)\Pinduoduo\Pinduoduo.exe",
            r"%LOCALAPPDATA%\Programs\Pinduoduo\Pinduoduo.exe",
        ),
    ),
    "xianyu": PlatformHints(
        label="闲鱼",
        keywords=("闲鱼", "咸鱼", "Xianyu", "Goofish", "Idle Fish"),
        common_paths=(
            r"C:\Program Files\Xianyu\Xianyu.exe",
            r"C:\Program Files (x86)\Xianyu\Xianyu.exe",
            r"%LOCALAPPDATA%\Programs\Xianyu\Xianyu.exe",
            r"C:\Program Files\Goofish\Goofish.exe",
            r"C:\Program Files (x86)\Goofish\Goofish.exe",
            r"%LOCALAPPDATA%\Programs\Goofish\Goofish.exe",
        ),
    ),
}


def expand_path(path: str) -> Path:
    return Path(os.path.expandvars(path)).expanduser()


def platform_patterns(platform: str) -> list[str]:
    info = PLATFORMS["douyin" if platform == "douyin_dm" else platform]
    return [str(pattern) for pattern in info["allowlist"]]


def title_matches(platform: str, title: str) -> bool:
    return any(re.search(pattern, title, re.IGNORECASE) for pattern in platform_patterns(platform))


def safe_enum_visible_windows() -> list[tuple[int, str]]:
    if os.name != "nt":
        return []
    try:
        return enum_visible_windows()
    except Exception:
        return []


def start_menu_dirs() -> list[Path]:
    candidates = [
        Path(os.environ.get("APPDATA", "")) / r"Microsoft\Windows\Start Menu\Programs",
        Path(os.environ.get("PROGRAMDATA", "")) / r"Microsoft\Windows\Start Menu\Programs",
        Path.home() / r"Desktop",
        Path(os.environ.get("PUBLIC", r"C:\Users\Public")) / "Desktop",
    ]
    return [path for path in candidates if path.exists()]


def find_shortcuts(hints: PlatformHints) -> list[Path]:
    found: list[Path] = []
    lowered_keywords = tuple(keyword.lower() for keyword in hints.keywords)
    blocked_words = ("卸载", "uninstall", "remove", "开发者工具", "developer", "devtools")
    for base in start_menu_dirs():
        try:
            for item in base.rglob("*"):
                if item.suffix.lower() not in {".lnk", ".url", ".exe"}:
                    continue
                name = item.name.lower()
                if any(word in name for word in blocked_words):
                    continue
                if any(keyword.lower() in name for keyword in lowered_keywords):
                    found.append(item)
        except OSError:
            continue
    return dedupe_paths(found)


def find_common_paths(hints: PlatformHints) -> list[Path]:
    return dedupe_paths([path for raw in hints.common_paths if (path := expand_path(raw)).exists()])


def dedupe_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        key = str(path).lower()
        if key not in seen:
            seen.add(key)
            result.append(path)
    return result


def discover_candidates(platform: str) -> list[Path]:
    hints = PLATFORM_HINTS[platform]
    return dedupe_paths(find_common_paths(hints) + find_shortcuts(hints))


def launch_candidate(path: Path) -> dict[str, Any]:
    try:
        os.startfile(str(path))  # type: ignore[attr-defined]
        return {"ok": True, "path": str(path)}
    except Exception as exc:
        try:
            subprocess.Popen([str(path)], close_fds=True)
            return {"ok": True, "path": str(path)}
        except Exception as inner_exc:
            return {"ok": False, "path": str(path), "error": f"{exc}; {inner_exc}"}


def matching_windows(platform: str, windows: list[tuple[int, str]]) -> list[dict[str, Any]]:
    return [
        {"hwnd": hwnd, "title": title}
        for hwnd, title in windows
        if title_matches(platform, title)
    ]


def guidance_for(platform: str, has_window: bool, has_candidate: bool) -> str:
    if has_window:
        return "已找到平台窗口。下一步请进入真实客服聊天页，再运行“验收真实平台.bat”。"
    if has_candidate:
        return "已找到可启动程序，但还没有客服聊天窗口。可用 --launch 自动启动，登录后进入聊天页。"
    if platform == "douyin":
        return "未找到桌面客户端。可以先在 Chrome 打开抖音企业号/巨量/商家后台客服页面，再重新巡检。"
    if platform == "taobao":
        return "未找到千牛。请安装并登录千牛工作台，打开买家咨询聊天窗口后重新巡检。"
    if platform == "pdd":
        return "未找到拼多多商家端。请安装商家工作台或在浏览器打开商家后台客服页面后重新巡检。"
    if platform == "xianyu":
        return "未找到闲鱼客服窗口。请打开闲鱼客户端或浏览器闲鱼消息/卖家聊天页后重新巡检。"
    return "未找到微信或企业微信。请安装并登录，打开真实聊天窗口后重新巡检。"


def run_prepare(platforms: list[str], launch: bool, wait_seconds: float) -> dict[str, Any]:
    initial_windows = safe_enum_visible_windows()
    results: dict[str, Any] = {}

    for platform in platforms:
        if platform not in PLATFORM_HINTS:
            results[platform] = {"ok": False, "status": "unsupported_platform"}
            continue
        candidates = discover_candidates(platform)
        windows = matching_windows(platform, initial_windows)
        launch_result: dict[str, Any] | None = None
        if launch and not windows and candidates:
            launch_result = launch_candidate(candidates[0])

        results[platform] = {
            "ok": bool(windows),
            "status": "window_found" if windows else "launch_attempted" if launch_result else "needs_open_chat_window",
            "label": PLATFORM_HINTS[platform].label,
            "expected_title_patterns": platform_patterns(platform),
            "windows": windows,
            "candidates": [str(path) for path in candidates[:8]],
            "launch": launch_result,
            "guidance": guidance_for(platform, bool(windows), bool(candidates)),
        }

    if launch and wait_seconds > 0:
        time.sleep(wait_seconds)
        refreshed_windows = safe_enum_visible_windows()
        for platform, item in results.items():
            windows = matching_windows(platform, refreshed_windows)
            if windows:
                item["ok"] = True
                item["status"] = "window_found_after_launch"
                item["windows"] = windows
                item["guidance"] = guidance_for(platform, True, bool(item.get("candidates")))

    return {
        "ok": all(item.get("ok") for item in results.values()) if results else False,
        "platforms": results,
        "desktop_environment": os.name == "nt",
        "visible_platform_windows": [
            title
            for _, title in safe_enum_visible_windows()
            if any(keyword.lower() in title.lower() for hints in PLATFORM_HINTS.values() for keyword in hints.keywords)
        ],
    }


def write_report(result: dict[str, Any], report_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 桌面客服平台自动巡检报告",
        "",
        "这个报告只负责准备和排查平台窗口，不会替你发送消息。",
        "真正验收自动读取请打开真实聊天页后运行 `验收真实平台.bat`。",
        "",
        "## 平台状态",
        "",
    ]
    for platform, item in result.get("platforms", {}).items():
        lines.append(f"### {item.get('label', platform)}")
        lines.append("")
        lines.append(f"- 状态：`{item.get('status')}`")
        lines.append(f"- 建议：{item.get('guidance')}")
        windows = item.get("windows") or []
        if windows:
            lines.append("- 已找到窗口：")
            for window in windows:
                lines.append(f"  - {window.get('title')}")
        else:
            lines.append("- 已找到窗口：无")
        candidates = item.get("candidates") or []
        if candidates:
            lines.append("- 可启动程序/快捷方式：")
            for candidate in candidates:
                lines.append(f"  - `{candidate}`")
        else:
            lines.append("- 可启动程序/快捷方式：未找到")
        launch = item.get("launch")
        if launch:
            lines.append(f"- 自动启动：`{launch}`")
        lines.append("")
    lines.append("## 下一步")
    lines.append("")
    lines.append("1. 打开对应平台的真实客服聊天页。")
    lines.append("2. 双击 `验收真实平台.bat`，看到平台状态为 `ok`。")
    lines.append("3. 双击 `启动AI自动客服.bat`，选择该聊天窗口开始监听。")
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="自动巡检/准备微信、企业微信、抖音、千牛、拼多多、闲鱼客服窗口。")
    parser.add_argument("--platforms", default=",".join(DEFAULT_PLATFORMS), help="逗号分隔：wechat,wechat_work,douyin,taobao,pdd,xianyu")
    parser.add_argument("--launch", action="store_true", help="找不到窗口时，尝试启动已安装的客户端或快捷方式。")
    parser.add_argument("--soft", action="store_true", help="即使平台窗口没全部准备好，也返回 0；用于普通验收和巡检报告。")
    parser.add_argument("--wait-seconds", type=float, default=3)
    parser.add_argument("--report", default=str(REPORT_PATH), help="中文报告输出路径。")
    args = parser.parse_args()

    platforms = [item.strip() for item in args.platforms.split(",") if item.strip()]
    result = run_prepare(platforms, args.launch, args.wait_seconds)
    report_path = Path(args.report)
    write_report(result, report_path)
    result["report"] = str(report_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if (result.get("ok") or args.soft) else 2


if __name__ == "__main__":
    raise SystemExit(main())
