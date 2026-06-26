from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MINIAPP = ROOT / "douyin-miniapp"


def load_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> None:
    required = [
        "app.json",
        "app.js",
        "app.ttss",
        "project.config.json",
        "utils/api.js",
        "pages/index/index.js",
        "pages/index/index.ttml",
        "pages/index/index.ttss",
        "pages/index/index.json",
        "pages/cases/cases.js",
        "pages/cases/cases.ttml",
        "pages/cases/cases.ttss",
        "pages/cases/cases.json",
        "pages/result/result.js",
        "pages/result/result.ttml",
        "pages/result/result.ttss",
        "pages/result/result.json",
        "pages/lead/lead.js",
        "pages/lead/lead.ttml",
        "pages/lead/lead.ttss",
        "pages/lead/lead.json",
    ]
    missing = [item for item in required if not (MINIAPP / item).exists()]
    if missing:
        raise SystemExit(f"Missing miniapp files: {missing}")

    app_json = load_json(MINIAPP / "app.json")
    project_json = load_json(MINIAPP / "project.config.json")
    pages = set(app_json.get("pages", []))
    expected_pages = {
        "pages/index/index",
        "pages/cases/cases",
        "pages/result/result",
        "pages/lead/lead",
    }
    if pages != expected_pages:
        raise SystemExit(f"Unexpected pages: {sorted(pages)}")

    appid = str(project_json.get("appid", ""))
    if not appid:
        raise SystemExit("project.config.json appid is empty")

    app_js = (MINIAPP / "app.js").read_text(encoding="utf-8")
    api_js = (MINIAPP / "utils/api.js").read_text(encoding="utf-8")
    if "https://wjhai.cn/merchant-admin/api" not in app_js:
        raise SystemExit("Missing apiBase in app.js")
    for needle in ["tt.request", "/scripts", "/leads"]:
        if needle not in api_js:
            raise SystemExit(f"Missing API marker: {needle}")

    print("Douyin miniapp static validation passed.")


if __name__ == "__main__":
    main()
