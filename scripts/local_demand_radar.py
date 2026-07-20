from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


DEFAULT_ROOTS = [
    "docs",
    "运营计划",
    "product-kit",
    "douyin-miniapp",
    "codex-plugins-marketplace",
    "src",
    "backend",
    "scripts",
]

SKIP_DIRS = {
    ".git",
    ".agents",
    ".codex",
    "node_modules",
    "dist",
    "__pycache__",
    "system-optimization-backup",
    "github-publish",
}

EXTENSIONS = {
    ".md",
    ".txt",
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".json",
    ".html",
    ".ttml",
    ".ttss",
    ".css",
}

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "AI客服": ["客服", "自动回复", "话术", "会话", "知识库", "微信", "抖音", "淘宝", "拼多多", "闲鱼", "小店"],
    "获客运营": ["获客", "线索", "客户", "私域", "引流", "抖音号", "转化", "矩阵", "企业号", "表单"],
    "图文视频生成": ["图片", "主图", "详情图", "视频", "短视频", "剪辑", "画布", "素材", "HyperFrames", "Remotion"],
    "小程序系统": ["小程序", "订阅", "留资", "上架", "抖音开发者", "微信生态", "TTML"],
    "文件需求挖掘": ["需求", "扫描", "文件", "仓库", "归类", "检索", "项目"],
    "部署交付": ["部署", "服务器", "域名", "验收", "README", "Docker", "API", "接口"],
}

HIGH_INTENT_WORDS = [
    "必须",
    "今天",
    "商用",
    "验收",
    "落地",
    "赚钱",
    "客户",
    "断客",
    "全自动",
    "官方API",
    "无bug",
    "部署",
]


@dataclass
class DemandHit:
    score: int
    category: str
    title: str
    path: str
    evidence: str
    recommendation: str
    monetization: str


def read_text(path: Path) -> str:
    raw = path.read_bytes()[:300_000]
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return raw.decode(encoding, errors="strict")
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def iter_files(root: Path, roots: Iterable[str]) -> Iterable[Path]:
    for item in roots:
        base = (root / item).resolve()
        if not base.exists():
            continue
        if base.is_file():
            yield base
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in EXTENSIONS:
                continue
            rel_parts = path.relative_to(root).parts
            if any(part in SKIP_DIRS for part in rel_parts):
                continue
            yield path


def short_evidence(text: str, keywords: list[str]) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        if any(word.lower() in line.lower() for word in keywords):
            clean = re.sub(r"\s+", " ", line)
            return clean[:180]
    return re.sub(r"\s+", " ", text[:180])


def recommendation_for(category: str) -> tuple[str, str]:
    if category == "AI客服":
        return (
            "优先做网页客服自动回复 + 桌面辅助回复；官方 API 到位后再切抖音小店/微信客服自动发送。",
            "按商家订阅收费，Starter 99/月，Pro 299/月，私有化部署 1999 起。",
        )
    if category == "获客运营":
        return (
            "用企业号线索表单、评论私信承接、手动/授权导入客户表，禁止无授权抓取联系方式。",
            "卖代运营启动包、获客 SOP、线索清洗和客服承接服务。",
        )
    if category == "图文视频生成":
        return (
            "先做主图/详情图/短视频脚本和画布模板，渲染服务后置接 HyperFrames/Remotion。",
            "按生成次数、模板包、行业素材包收费。",
        )
    if category == "小程序系统":
        return (
            "先做线索收集/AI客服入口小程序，避免重做复杂交易系统，快速上架验证需求。",
            "卖行业小程序模板 + 年费维护 + 私域部署。",
        )
    if category == "文件需求挖掘":
        return (
            "把本地资料扫描成需求雷达，按高频词和商用紧急度生成项目优先级。",
            "作为咨询交付物和项目立项工具，提高成交可信度。",
        )
    return (
        "整理为可复制部署包、验收脚本、客户教程，减少交付返工。",
        "卖部署服务、二开服务和月度运维。",
    )


def scan_paths(root: Path, roots: Iterable[str]) -> list[DemandHit]:
    hits: list[DemandHit] = []
    for path in iter_files(root, roots):
        try:
            text = read_text(path)
        except OSError:
            continue
        if len(text.strip()) < 30:
            continue
        lower = text.lower()
        category_scores: Counter[str] = Counter()
        for category, words in CATEGORY_KEYWORDS.items():
            for word in words:
                count = lower.count(word.lower())
                if count:
                    category_scores[category] += count
        if not category_scores:
            continue
        category, base_score = category_scores.most_common(1)[0]
        intent_score = sum(lower.count(word.lower()) * 3 for word in HIGH_INTENT_WORDS)
        score = min(100, base_score + intent_score)
        if score < 4:
            continue
        recommendation, monetization = recommendation_for(category)
        rel = str(path.relative_to(root))
        title = f"{category} - {path.stem}"
        hits.append(
            DemandHit(
                score=score,
                category=category,
                title=title,
                path=rel,
                evidence=short_evidence(text, CATEGORY_KEYWORDS[category] + HIGH_INTENT_WORDS),
                recommendation=recommendation,
                monetization=monetization,
            )
        )
    hits.sort(key=lambda item: item.score, reverse=True)
    return hits


def write_outputs(root: Path, hits: list[DemandHit], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "需求雷达.json"
    csv_path = output_dir / "需求雷达.csv"
    md_path = output_dir / "需求雷达报告.md"

    json_path.write_text(json.dumps([asdict(hit) for hit in hits], ensure_ascii=False, indent=2), encoding="utf-8")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(hits[0]).keys()) if hits else ["score", "category", "title", "path", "evidence", "recommendation", "monetization"])
        writer.writeheader()
        for hit in hits:
            writer.writerow(asdict(hit))

    category_count = Counter(hit.category for hit in hits)
    lines = [
        "# 本地文件需求雷达报告",
        "",
        f"- 扫描时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 命中需求：{len(hits)} 条",
        "",
        "## 需求分类",
        "",
    ]
    for category, count in category_count.most_common():
        lines.append(f"- {category}：{count} 条")
    lines.extend(["", "## Top 20 高优先级需求", ""])
    for index, hit in enumerate(hits[:20], 1):
        lines.extend(
            [
                f"### {index}. {hit.title}（{hit.score}分）",
                f"- 文件：`{hit.path}`",
                f"- 证据：{hit.evidence}",
                f"- 建议：{hit.recommendation}",
                f"- 变现：{hit.monetization}",
                "",
            ]
        )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return {"json": str(json_path), "csv": str(csv_path), "md": str(md_path)}


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="Scan local project files and produce a commercial demand radar report.")
    parser.add_argument("--roots", default=",".join(DEFAULT_ROOTS), help="Comma-separated relative folders to scan.")
    parser.add_argument("--output-dir", default="运营计划/今日交付包/需求雷达", help="Output directory.")
    parser.add_argument("--limit", type=int, default=200, help="Max rows to keep.")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    roots = [item.strip() for item in args.roots.split(",") if item.strip()]
    hits = scan_paths(root, roots)[: args.limit]
    outputs = write_outputs(root, hits, root / args.output_dir)
    print(json.dumps({"ok": True, "count": len(hits), "outputs": outputs}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
