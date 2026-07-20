from __future__ import annotations

import json
from pathlib import Path
import re


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
    for needle in ["tt.request", "/scripts", "/leads", "/product-media/pack", "generateProductMediaPack"]:
        if needle not in api_js:
            raise SystemExit(f"Missing API marker: {needle}")

    index_js = (MINIAPP / "pages/index/index.js").read_text(encoding="utf-8")
    result_js = (MINIAPP / "pages/result/result.js").read_text(encoding="utf-8")
    result_ttml = (MINIAPP / "pages/result/result.ttml").read_text(encoding="utf-8")
    index_ttml = (MINIAPP / "pages/index/index.ttml").read_text(encoding="utf-8")
    cases_ttml = (MINIAPP / "pages/cases/cases.ttml").read_text(encoding="utf-8")
    lead_ttml = (MINIAPP / "pages/lead/lead.ttml").read_text(encoding="utf-8")
    lead_js = (MINIAPP / "pages/lead/lead.js").read_text(encoding="utf-8")
    for path_name, content, markers in [
        ("utils/api.js", api_js, ["generateManagedOpsPlan", "miniapp_template", "/product-media/pack"]),
        ("pages/index/index.js", index_js, ["generateProductMediaPack", "generateManagedOpsPlan", "ecommerce_brief"]),
        ("pages/cases/cases.js", (MINIAPP / "pages/cases/cases.js").read_text(encoding="utf-8"), ["ecommerce_brief", "platform: 'douyin'", "platform: 'pdd'"]),
        ("pages/result/result.js", result_js, ["generateProductMediaPack", "generateManagedOpsPlan", "managedPlan", "copyPlan"]),
        ("pages/result/result.ttml", result_ttml, ["mediaPack.main_image_url", "mediaPack.detail_image_url", "mediaPack.video_url", "managedPlan.price_packages", "请求真实主图"]),
        ("pages/lead/lead.js", lead_js, ["createLead", "catch (error)", "提交失败"]),
    ]:
        for marker in markers:
            if marker not in content:
                raise SystemExit(f"Missing miniapp product media marker in {path_name}: {marker}")

    page_pairs = [
        ("pages/index/index", index_ttml, index_js),
        ("pages/cases/cases", cases_ttml, (MINIAPP / "pages/cases/cases.js").read_text(encoding="utf-8")),
        ("pages/result/result", result_ttml, result_js),
        ("pages/lead/lead", lead_ttml, lead_js),
    ]
    for page_name, ttml, js in page_pairs:
        handlers = set(re.findall(r'bindtap="([^"]+)"', ttml))
        missing_handlers = [handler for handler in sorted(handlers) if f"{handler}(" not in js]
        if missing_handlers:
            raise SystemExit(f"Missing bindtap handlers in {page_name}: {missing_handlers}")

    forbidden_text = ["自动发布商品", "自动修改价格", "自动退款", "保证成交", "保证收益"]
    visible_text = "\n".join([index_ttml, cases_ttml, result_ttml, lead_ttml, (MINIAPP / "README.md").read_text(encoding="utf-8")])
    for phrase in forbidden_text:
        if phrase in visible_text and f"不{phrase}" not in visible_text:
            raise SystemExit(f"Potentially misleading launch text: {phrase}")

    print("Douyin miniapp static validation passed.")


if __name__ == "__main__":
    main()
