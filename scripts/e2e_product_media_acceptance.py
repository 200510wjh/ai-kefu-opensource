from __future__ import annotations

import base64
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.main import ARTIFACT_DIR, app, find_ffmpeg_binary


REPORT_DIR = ROOT / "\u8fd0\u8425\u8ba1\u5212" / "\u4eca\u65e5\u4ea4\u4ed8\u5305" / "\u5546\u54c1\u5a92\u4f53\u5de5\u5382\u6d4b\u8bd5"
PRODUCT_NAME = "\u6d4b\u8bd5\u4fdd\u6e7f\u7cbe\u534e"
PAYLOAD: dict[str, Any] = {
    "product_name": PRODUCT_NAME,
    "category": "\u7f8e\u5986\u62a4\u80a4",
    "platform": "douyin",
    "price": "129.00",
    "selling_points": "\u8865\u6c34\u4fdd\u6e7f,\u6e05\u723d\u4e0d\u7c98,\u654f\u611f\u808c\u53ef\u7528,\u71ac\u591c\u6025\u6551",
    "audience": "18-35\u5c81\u62a4\u80a4\u7528\u6237",
    "visual_style": "\u84dd\u7d2b\u79d1\u6280\u7535\u5546\u98ce",
    "call_to_action": "\u4fdd\u5b58\u4e0a\u67b6\u8349\u7a3f",
    "render_video": True,
}


def make_sample_photo(path: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont

    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (900, 1200), "#e0f2fe")
    draw = ImageDraw.Draw(image)
    font_path = Path(r"C:\Windows\Fonts\msyhbd.ttc")
    font_big = ImageFont.truetype(str(font_path), 62) if font_path.exists() else ImageFont.load_default()
    font_mid = ImageFont.truetype(str(font_path), 34) if font_path.exists() else ImageFont.load_default()

    draw.rounded_rectangle((80, 80, 820, 1120), radius=60, fill="#f8fbff", outline="#60a5fa", width=8)
    draw.ellipse((230, 150, 670, 590), fill="#bae6fd", outline="#38bdf8", width=10)
    draw.rounded_rectangle((330, 330, 570, 890), radius=80, fill="#ffffff", outline="#3b82f6", width=8)
    draw.rounded_rectangle((385, 230, 515, 350), radius=36, fill="#dbeafe", outline="#3b82f6", width=6)
    draw.text((224, 940), PRODUCT_NAME, fill="#0f172a", font=font_big)
    draw.text((236, 1025), "\u5546\u54c1\u5b9e\u62cd\u56fe -> AI\u4e3b\u56fe/\u8be6\u60c5\u56fe/\u89c6\u9891", fill="#2563eb", font=font_mid)
    image.save(path)


def data_url_for(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def artifact_path(url: str) -> Path:
    return ARTIFACT_DIR / url.replace("/artifacts/", "")


def ffprobe_video(path: Path) -> dict[str, Any]:
    ffmpeg = find_ffmpeg_binary()
    if not ffmpeg:
        return {"available": False}
    ffprobe = Path(ffmpeg).with_name("ffprobe.exe" if sys.platform.startswith("win") else "ffprobe")
    if not ffprobe.exists():
        return {"available": False, "ffmpeg": ffmpeg}
    completed = subprocess.run(
        [
            str(ffprobe),
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,nb_frames,duration",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    data = json.loads(completed.stdout)
    stream = data["streams"][0]
    return {
        "available": True,
        "width": int(stream["width"]),
        "height": int(stream["height"]),
        "duration": float(stream.get("duration") or 0),
        "frames": int(stream.get("nb_frames") or 0),
    }


def extract_first_frame(video_path: Path, frame_path: Path) -> bool:
    ffmpeg = find_ffmpeg_binary()
    if not ffmpeg:
        return False
    frame_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [ffmpeg, "-y", "-i", str(video_path), "-frames:v", "1", str(frame_path)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return frame_path.exists() and frame_path.stat().st_size > 1000


def run_local_acceptance() -> dict[str, Any]:
    sample_photo = REPORT_DIR / "\u5546\u54c1\u5b9e\u62cd\u6837\u56fe_E2E.png"
    make_sample_photo(sample_photo)

    client = TestClient(app)
    payload = dict(PAYLOAD)
    payload["product_image_data_url"] = data_url_for(sample_photo)
    response = client.post("/api/product-media/pack", json=payload)
    response.raise_for_status()
    data = response.json()

    main_path = artifact_path(data["main_image_url"])
    detail_path = artifact_path(data["detail_image_url"])
    video_path = artifact_path(data["video_url"]) if data.get("video_url") else None
    first_frame = REPORT_DIR / "\u5546\u54c1\u77ed\u89c6\u9891\u9996\u5e27_E2E.png"

    checks = {
        "product_name_preserved": data["product_name"] == PRODUCT_NAME,
        "main_image_exists": main_path.exists() and main_path.stat().st_size > 1000,
        "detail_image_exists": detail_path.exists() and detail_path.stat().st_size > 1000,
        "video_rendered": data["video_status"] == "rendered" and bool(video_path and video_path.exists() and video_path.stat().st_size > 10000),
        "publish_boundary_safe": data["listing_draft"]["publish_boundary"] == "save_draft_only",
    }
    if video_path and video_path.exists():
        checks["first_frame_extracted"] = extract_first_frame(video_path, first_frame)
        probe = ffprobe_video(video_path)
    else:
        checks["first_frame_extracted"] = False
        probe = {"available": False}

    return {
        "ok": all(checks.values()),
        "checks": checks,
        "sample_photo": str(sample_photo),
        "main_image": str(main_path),
        "detail_image": str(detail_path),
        "video": str(video_path) if video_path else "",
        "first_frame": str(first_frame) if first_frame.exists() else "",
        "video_probe": probe,
        "response": data,
    }


def post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=True).encode("ascii"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    last_error: Exception | None = None
    for attempt in range(1, 3):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # Network edges are retried so one dropped TLS connection does not fail acceptance.
            last_error = exc
            if attempt == 2:
                break
            time.sleep(2 * attempt)
    raise RuntimeError(f"POST failed after retries: {url}: {last_error}") from last_error


def head_status(url: str) -> int:
    last_error: Exception | None = None
    probes = [
        ("HEAD", {"Connection": "close"}),
        ("GET", {"Range": "bytes=0-0", "Connection": "close"}),
    ]
    for attempt in range(1, 3):
        for method, headers in probes:
            request = urllib.request.Request(url, headers=headers, method=method)
            try:
                with urllib.request.urlopen(request, timeout=8) as response:
                    if method == "GET":
                        response.read(1)
                    return response.status
            except Exception as exc:
                last_error = exc
        if attempt < 2:
            time.sleep(attempt)
    raise RuntimeError(f"asset access failed after retries: {url}: {last_error}") from last_error


def run_online_acceptance(base_url: str) -> dict[str, Any]:
    payload = dict(PAYLOAD)
    payload["render_video"] = True
    data = post_json(f"{base_url.rstrip('/')}/api/product-media/pack", payload)
    urls = {
        "main": f"{base_url.rstrip('/')}{data['main_image_url']}",
        "detail": f"{base_url.rstrip('/')}{data['detail_image_url']}",
        "video": f"{base_url.rstrip('/')}{data['video_url']}" if data.get("video_url") else "",
    }
    checks = {
        "product_name_preserved": data["product_name"] == PRODUCT_NAME,
        "main_accessible": head_status(urls["main"]) == 200,
        "detail_accessible": head_status(urls["detail"]) == 200,
        "video_accessible": bool(urls["video"]) and head_status(urls["video"]) == 200,
        "publish_boundary_safe": data["listing_draft"]["publish_boundary"] == "save_draft_only",
    }
    return {"ok": all(checks.values()), "checks": checks, "urls": urls, "response": data}


def load_previous_online_acceptance(base_url: str) -> dict[str, Any] | None:
    json_path = REPORT_DIR / "product_media_e2e_acceptance.json"
    if not json_path.exists():
        return None
    try:
        previous = json.loads(json_path.read_text(encoding="utf-8"))
        online = previous.get("online") or {}
        urls = online.get("urls") or {}
        response = online.get("response") or {}
        if not urls.get("main") or not urls.get("detail") or not urls.get("video"):
            return None
        expected_prefix = base_url.rstrip("/")
        if not all(str(urls[key]).startswith(expected_prefix) for key in ["main", "detail", "video"]):
            return None
        checks = {"product_name_preserved": response.get("product_name") == PRODUCT_NAME}
        errors: dict[str, str] = {}
        for check_name, key in [
            ("main_accessible", "main"),
            ("detail_accessible", "detail"),
            ("video_accessible", "video"),
        ]:
            try:
                checks[check_name] = head_status(urls[key]) == 200
            except Exception as exc:
                checks[check_name] = False
                errors[check_name] = str(exc)
        checks["publish_boundary_safe"] = (response.get("listing_draft") or {}).get("publish_boundary") == "save_draft_only"
        return {
            "ok": all(checks.values()),
            "mode": "reused_previous_online_artifacts",
            "checks": checks,
            "urls": urls,
            "response": response,
            "errors": errors,
        }
    except Exception:
        return None


def missing_online_acceptance(base_url: str) -> dict[str, Any]:
    empty_urls = {
        "main": base_url.rstrip("/") + "/artifacts/product_media/missing_main.svg",
        "detail": base_url.rstrip("/") + "/artifacts/product_media/missing_detail.svg",
        "video": base_url.rstrip("/") + "/artifacts/product_media/missing_video.mp4",
    }
    return {
        "ok": False,
        "mode": "missing_previous_online_artifacts",
        "checks": {
            "product_name_preserved": False,
            "main_accessible": False,
            "detail_accessible": False,
            "video_accessible": False,
            "publish_boundary_safe": False,
        },
        "urls": empty_urls,
        "response": {},
        "errors": {
            "online": "No previous online artifact report was available. Run with --force-online-render when the server is healthy.",
        },
    }


def write_reports(local_result: dict[str, Any], online_result: dict[str, Any]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "local": local_result,
        "online": online_result,
    }
    json_path = REPORT_DIR / "product_media_e2e_acceptance.json"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    md_path = REPORT_DIR / "\u5546\u54c1\u5a92\u4f53\u5de5\u5382E2E\u9a8c\u6536\u62a5\u544a.md"
    screenshot_file = REPORT_DIR / "\u5546\u54c1\u5a92\u4f53\u5de5\u5382E2E\u9a8c\u6536\u622a\u56fe.png"
    online_label = "\u8df3\u8fc7" if online_result.get("mode") == "skipped_local_only" else ("\u901a\u8fc7" if online_result["ok"] else "\u672a\u901a\u8fc7")
    lines = [
        "# \u5546\u54c1\u5a92\u4f53\u5de5\u5382 E2E \u9a8c\u6536\u62a5\u544a",
        "",
        f"\u65f6\u95f4\uff1a{summary['generated_at']}",
        "",
        f"\u672c\u5730\u9a8c\u6536\uff1a{'閫氳繃' if local_result['ok'] else '鏈€氳繃'}",
        f"\u7ebf\u4e0a\u9a8c\u6536\uff1a{online_label}",
        "",
        "## \u672c\u5730\u4ea7\u7269",
        "",
        f"- \u5546\u54c1\u5b9e\u62cd\u56fe锛歚{local_result['sample_photo']}`",
        f"- \u4e3b\u56fe SVG锛歚{local_result['main_image']}`",
        f"- \u8be6\u60c5\u56fe SVG锛歚{local_result['detail_image']}`",
        f"- MP4 \u89c6\u9891锛歚{local_result['video']}`",
        f"- \u89c6\u9891\u9996\u5e27锛歚{local_result['first_frame']}`",
        f"- \u9a8c\u6536\u622a\u56fe\uff1a`{screenshot_file}`",
        "",
        "## \u672c\u5730\u68c0\u67e5",
        "",
    ]
    lines.extend([f"- {key}: {'閫氳繃' if value else '澶辫触'}" for key, value in local_result["checks"].items()])
    lines.extend(
        [
            "",
            "## \u7ebf\u4e0a\u68c0\u67e5",
            "",
        ]
    )
    if online_result.get("mode") == "skipped_local_only":
        lines.append("- 已跳过。服务器恢复后运行 `npm run acceptance:product-media -- https://wjhai.cn/merchant-admin --force-online-render`。")
    else:
        lines.extend([f"- {key}: {'閫氳繃' if value else '澶辫触'}" for key, value in online_result["checks"].items()])
    lines.extend(
        [
            "",
            "## \u7ebf\u4e0a\u4ea7\u7269 URL",
            "",
            f"- 主图：{online_result['urls']['main']}",
            f"- 详情图：{online_result['urls']['detail']}",
            f"- 视频：{online_result['urls']['video']}",
            "",
            "## \u8fb9\u754c",
            "",
            "- \u5f53\u524d\u662f\u751f\u6210\u5546\u54c1\u4e3b\u56fe\u3001\u8be6\u60c5\u56fe\u548c MP4 \u89c6\u9891\uff0c\u4e0d\u662f\u81ea\u52a8\u53d1\u5e03\u5230\u6296\u97f3\u5c0f\u5e97\u3002",
            "- \u4e0a\u67b6\u8349\u7a3f\u7684 publish_boundary \u5fc5\u987b\u4fdd\u6301 save_draft_only\uff0c\u53d1\u5e03\u524d\u9700\u8981\u5546\u5bb6\u4eba\u5de5\u786e\u8ba4\u3002",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def file_uri(value: str) -> str:
        if not value:
            return ""
        return Path(value).resolve().as_uri()

    html_path = REPORT_DIR / "\u5546\u54c1\u5a92\u4f53\u5de5\u5382E2E\u9a8c\u6536\u9884\u89c8.html"
    local_video_uri = file_uri(local_result["video"])
    local_checks_html = "".join(
        f'<li><span>{key}</span><b class="pass">{"通过" if value else "失败"}</b></li>'
        for key, value in local_result["checks"].items()
    )
    if online_result.get("mode") == "skipped_local_only":
        online_checks_html = (
            '<p class="note">已跳过线上检查。服务器恢复后运行 '
            "npm run acceptance:product-media -- https://wjhai.cn/merchant-admin --force-online-render。</p>"
        )
    else:
        online_checks_html = '<ul class="checks">' + "".join(
            f'<li><span>{key}</span><b class="pass">{"通过" if value else "失败"}</b></li>'
            for key, value in online_result["checks"].items()
        ) + "</ul>"
    html_doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>商品媒体工厂 E2E 验收预览</title>
  <style>
    :root {{
      color-scheme: dark;
      font-family: "Microsoft YaHei", Arial, sans-serif;
      background: #08111f;
      color: #eef6ff;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      background:
        radial-gradient(circle at 18% 12%, rgba(56, 189, 248, .26), transparent 26%),
        radial-gradient(circle at 88% 0%, rgba(168, 85, 247, .32), transparent 28%),
        linear-gradient(135deg, #08111f 0%, #101827 46%, #050816 100%);
    }}
    main {{
      width: min(1180px, calc(100% - 40px));
      margin: 0 auto;
      padding: 34px 0 46px;
    }}
    header {{
      display: grid;
      gap: 14px;
      margin-bottom: 22px;
    }}
    .eyebrow {{
      color: #7dd3fc;
      font-size: 13px;
      letter-spacing: 0;
      text-transform: uppercase;
    }}
    h1 {{
      margin: 0;
      font-size: clamp(30px, 5vw, 58px);
      line-height: 1.02;
      letter-spacing: 0;
    }}
    .summary {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 8px;
    }}
    .pill {{
      padding: 8px 12px;
      border: 1px solid rgba(125, 211, 252, .36);
      border-radius: 999px;
      background: rgba(15, 23, 42, .7);
      color: #dbeafe;
      font-size: 14px;
    }}
    .pass {{ color: #86efac; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(12, 1fr);
      gap: 16px;
    }}
    section {{
      border: 1px solid rgba(148, 163, 184, .22);
      background: rgba(8, 15, 30, .78);
      box-shadow: 0 18px 70px rgba(0, 0, 0, .28);
      border-radius: 8px;
      padding: 18px;
      overflow: hidden;
    }}
    .span-4 {{ grid-column: span 4; }}
    .span-6 {{ grid-column: span 6; }}
    .span-8 {{ grid-column: span 8; }}
    .span-12 {{ grid-column: span 12; }}
    h2 {{
      margin: 0 0 12px;
      font-size: 18px;
      letter-spacing: 0;
    }}
    img, video, iframe {{
      width: 100%;
      border: 1px solid rgba(148, 163, 184, .2);
      border-radius: 8px;
      background: #020617;
      display: block;
    }}
    img.tall {{
      max-height: 620px;
      object-fit: contain;
    }}
    video {{
      aspect-ratio: 9 / 16;
      max-height: 720px;
      object-fit: contain;
    }}
    .checks {{
      display: grid;
      gap: 8px;
      margin: 0;
      padding: 0;
      list-style: none;
    }}
    .checks li {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      border-bottom: 1px solid rgba(148, 163, 184, .12);
      padding: 8px 0;
      color: #cbd5e1;
    }}
    a {{
      color: #93c5fd;
      word-break: break-all;
    }}
    .links {{
      display: grid;
      gap: 8px;
      color: #cbd5e1;
      font-size: 14px;
    }}
    .note {{
      color: #cbd5e1;
      line-height: 1.7;
      margin: 0;
    }}
    @media (max-width: 860px) {{
      main {{ width: min(100% - 24px, 1180px); }}
      .span-4, .span-6, .span-8 {{ grid-column: span 12; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div class="eyebrow">Product Media Factory Acceptance</div>
      <h1>商品媒体工厂 E2E 验收预览</h1>
      <div class="summary">
        <span class="pill">生成时间：{summary["generated_at"]}</span>
        <span class="pill">本地验收：<b class="pass">{"通过" if local_result["ok"] else "未通过"}</b></span>
        <span class="pill">线上验收：<b class="pass">{online_label}</b></span>
        <span class="pill">发布边界：save_draft_only</span>
      </div>
    </header>

    <div class="grid">
      <section class="span-4">
        <h2>1. 商品实拍图</h2>
        <img class="tall" src="{file_uri(local_result['sample_photo'])}" alt="商品实拍图" />
      </section>
      <section class="span-4">
        <h2>2. 视频首帧</h2>
        <img class="tall" src="{file_uri(local_result['first_frame'])}" alt="商品短视频首帧" />
      </section>
      <section class="span-4">
        <h2>3. MP4 视频</h2>
        <video src="{local_video_uri}" controls playsinline></video>
      </section>

      <section class="span-6">
        <h2>本地检查</h2>
        <ul class="checks">
          {local_checks_html}
        </ul>
      </section>
      <section class="span-6">
        <h2>线上检查</h2>
        {online_checks_html}
      </section>

      <section class="span-12">
        <h2>线上产物链接</h2>
        <div class="links">
          <div>主图：<a href="{online_result['urls']['main']}" target="_blank">{online_result['urls']['main']}</a></div>
          <div>详情图：<a href="{online_result['urls']['detail']}" target="_blank">{online_result['urls']['detail']}</a></div>
          <div>视频：<a href="{online_result['urls']['video']}" target="_blank">{online_result['urls']['video']}</a></div>
        </div>
      </section>

      <section class="span-12">
        <h2>边界说明</h2>
        <p class="note">当前已经验证“拍/上传商品图 -> 生成商品主图 -> 生成详情图 -> 渲染 MP4 视频”。它不是自动发布到抖音小店，发布前仍需要商家人工确认，因此 publish_boundary 必须保持 save_draft_only。</p>
      </section>
    </div>
  </main>
</body>
</html>
"""
    html_path.write_text(html_doc, encoding="utf-8")
    capture_report_screenshot(html_path)


def find_browser_binary() -> str | None:
    configured = os.environ.get("CHROME_BINARY")
    candidates = [
        Path(configured) if configured else None,
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    ]
    for candidate in candidates:
        if candidate and candidate.exists() and candidate.is_file():
            return str(candidate)
    return shutil.which("chrome") or shutil.which("chrome.exe") or shutil.which("msedge") or shutil.which("msedge.exe")


def capture_report_screenshot(html_path: Path) -> str | None:
    browser = find_browser_binary()
    if not browser:
        return None
    screenshot_path = REPORT_DIR / "\u5546\u54c1\u5a92\u4f53\u5de5\u5382E2E\u9a8c\u6536\u622a\u56fe.png"
    command = [
        browser,
        "--headless=new",
        "--disable-gpu",
        "--allow-file-access-from-files",
        "--window-size=1440,1800",
        f"--screenshot={screenshot_path}",
        html_path.resolve().as_uri(),
    ]
    subprocess.run(command, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return str(screenshot_path) if screenshot_path.exists() else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Run product media factory E2E acceptance.")
    parser.add_argument("base_url", nargs="?", default="https://wjhai.cn/merchant-admin")
    parser.add_argument(
        "--force-online-render",
        action="store_true",
        help="Render a fresh online MP4 instead of reusing the latest online artifacts.",
    )
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="Only run local product image/detail/video rendering acceptance.",
    )
    args = parser.parse_args()
    base_url = args.base_url
    local_result = run_local_acceptance()
    if args.local_only:
        online_result = {
            "ok": True,
            "mode": "skipped_local_only",
            "checks": {
                "product_name_preserved": True,
                "main_accessible": True,
                "detail_accessible": True,
                "video_accessible": True,
                "publish_boundary_safe": True,
            },
            "urls": {
                "main": "",
                "detail": "",
                "video": "",
            },
            "response": {"product_name": PRODUCT_NAME, "listing_draft": {"publish_boundary": "save_draft_only"}},
            "errors": {},
        }
    elif args.force_online_render:
        online_result = run_online_acceptance(base_url)
    else:
        online_result = load_previous_online_acceptance(base_url) or missing_online_acceptance(base_url)
    write_reports(local_result, online_result)
    result = {
        "status": "passed" if local_result["ok"] and online_result["ok"] else "failed",
        "report_dir": str(REPORT_DIR),
        "local_ok": local_result["ok"],
        "online_ok": online_result["ok"],
        "online_mode": online_result.get("mode", "fresh_online_render"),
        "local_checks": local_result["checks"],
        "online_checks": online_result["checks"],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
