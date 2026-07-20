from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


def default_api_base() -> str:
    if os.getenv("MINIMAX_VIDEO_BASE_URL"):
        return os.getenv("MINIMAX_VIDEO_BASE_URL", "").rstrip("/")
    if os.getenv("MINIMAX_CN_API_KEY") and not (os.getenv("MINIMAX_API_KEY") or os.getenv("MINIMAX_VIDEO_API_KEY")):
        return "https://api.minimaxi.com/v1"
    return "https://api.minimax.io/v1"


API_BASE = default_api_base()


def api_key() -> str:
    key = (
        os.getenv("MINIMAX_VIDEO_API_KEY")
        or os.getenv("MINIMAX_API_KEY")
        or os.getenv("MINIMAX_CN_API_KEY")
    )
    if not key:
        raise SystemExit("Missing MINIMAX_VIDEO_API_KEY, MINIMAX_API_KEY, or MINIMAX_CN_API_KEY.")
    return key


def data_url(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def request_json(method: str, path: str, token: str, payload: dict[str, Any] | None = None, params: dict[str, Any] | None = None, timeout: int = 120) -> dict[str, Any]:
    url = f"{API_BASE}{path}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"MiniMax HTTP {exc.code}: {message}") from exc


def assert_ok(data: dict[str, Any], context: str) -> None:
    base = data.get("base_resp") or {}
    code = int(base.get("status_code") or 0)
    if code != 0:
        raise RuntimeError(f"{context} failed: {base.get('status_msg') or data}")


def create_task(image_path: Path, prompt: str, model: str, duration: int, resolution: str, prompt_optimizer: bool, token: str) -> str:
    payload = {
        "model": model,
        "first_frame_image": data_url(image_path),
        "prompt": prompt,
        "duration": duration,
        "resolution": resolution,
        "prompt_optimizer": prompt_optimizer,
    }
    data = request_json("POST", "/video_generation", token, payload=payload, timeout=180)
    assert_ok(data, "create video task")
    task_id = data.get("task_id")
    if not task_id:
        raise RuntimeError(f"MiniMax returned no task_id: {data}")
    return str(task_id)


def poll_task(task_id: str, token: str, interval: int, timeout_seconds: int) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    while True:
        data = request_json("GET", "/query/video_generation", token, params={"task_id": task_id}, timeout=60)
        assert_ok(data, "query video task")
        status = data.get("status")
        print(f"task {task_id}: {status}", flush=True)
        if status == "Success":
            return data
        if status == "Fail":
            raise RuntimeError(f"MiniMax task failed: {data}")
        if time.time() >= deadline:
            raise TimeoutError(f"Timed out waiting for MiniMax task {task_id}: {data}")
        time.sleep(interval)


def download_file(file_id: str, output: Path, token: str) -> str:
    data = request_json("GET", "/files/retrieve", token, params={"file_id": file_id}, timeout=60)
    assert_ok(data, "retrieve video file")
    file_info = data.get("file") or {}
    download_url = file_info.get("download_url")
    if not download_url:
        raise RuntimeError(f"MiniMax returned no download_url: {data}")
    with urllib.request.urlopen(str(download_url), timeout=180) as response:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(response.read())
    return str(download_url)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a real image-to-video clip using MiniMax Hailuo.")
    parser.add_argument("--image", required=True, type=Path, help="Local first-frame image.")
    parser.add_argument("--prompt", required=True, help="Motion prompt.")
    parser.add_argument("--out", required=True, type=Path, help="Output MP4 path.")
    parser.add_argument("--model", default=os.getenv("MINIMAX_VIDEO_MODEL", "MiniMax-Hailuo-2.3-Fast"))
    parser.add_argument("--duration", type=int, default=int(os.getenv("MINIMAX_VIDEO_DURATION", "6")))
    parser.add_argument("--resolution", default=os.getenv("MINIMAX_VIDEO_RESOLUTION", "768P"))
    parser.add_argument("--poll-interval", type=int, default=10)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--no-prompt-optimizer", action="store_true")
    args = parser.parse_args()

    token = api_key()
    image_path = args.image.resolve()
    if not image_path.exists():
        raise SystemExit(f"Image not found: {image_path}")
    task_id = create_task(
        image_path=image_path,
        prompt=args.prompt,
        model=args.model,
        duration=args.duration,
        resolution=args.resolution,
        prompt_optimizer=not args.no_prompt_optimizer,
        token=token,
    )
    print(f"submitted task_id={task_id}", flush=True)
    result = poll_task(task_id, token, args.poll_interval, args.timeout)
    file_id = result.get("file_id")
    if not file_id:
        raise RuntimeError(f"MiniMax success without file_id: {result}")
    download_file(str(file_id), args.out.resolve(), token)
    meta = {
        "task_id": task_id,
        "file_id": str(file_id),
        "model": args.model,
        "duration": args.duration,
        "resolution": args.resolution,
        "source_image": str(image_path),
        "output": str(args.out.resolve()),
        "prompt": args.prompt,
        "video_width": result.get("video_width"),
        "video_height": result.get("video_height"),
    }
    args.out.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.out.resolve(), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
