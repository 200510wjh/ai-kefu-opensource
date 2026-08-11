from __future__ import annotations

import argparse
import json
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.internal_growth.models import ContentTask, DemandSignal, PublishingRecord, now_iso
from backend.internal_growth.store import store


try:
    TZ = ZoneInfo("Asia/Shanghai")
except Exception:
    TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")
PACK_ROOT = ROOT / "output" / "douyin-daily"


@dataclass(frozen=True)
class ProjectSignal:
    key: str
    name: str
    path: Path
    status: str
    assets: list[str]
    insight: str
    audience: str
    offer: str
    score: int


@dataclass(frozen=True)
class Topic:
    key: str
    source: str
    title: str
    hook: str
    pain: str
    proof: str
    solution: str
    cta: str
    assets: list[str]
    score: int


def _read_text(path: Path, limit: int = 4000) -> str:
    if not path.exists() or not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:limit]
    except OSError:
        return ""


def _count_files(path: Path, suffixes: set[str]) -> int:
    if not path.exists():
        return 0
    return sum(
        1
        for item in path.rglob("*")
        if item.is_file() and item.suffix.lower() in suffixes and not item.name.startswith("_contact_sheet")
    )


def _latest_files(path: Path, suffixes: set[str], limit: int = 6) -> list[str]:
    if not path.exists():
        return []
    files = [
        item
        for item in path.rglob("*")
        if item.is_file() and item.suffix.lower() in suffixes and not item.name.startswith("_contact_sheet")
    ]
    files.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    return [str(item.relative_to(ROOT)) for item in files[:limit]]


def scan_project_signals() -> list[ProjectSignal]:
    signals: list[ProjectSignal] = []

    summit = ROOT / "峰会内容"
    summit_assets = _latest_files(summit, {".jpg", ".jpeg", ".png"}, 8)
    if summit.exists():
        signals.append(
            ProjectSignal(
                key="summit_ai_sop",
                name="峰会内容素材库",
                path=summit,
                status=f"{_count_files(summit, {'.jpg', '.jpeg', '.png'})} 张现场/PPT照片，可直接做真实观察类视频",
                assets=summit_assets,
                insight="企业客户不是想听AI概念，而是要降本、提效、线索、成交和可复制SOP。",
                audience="中小企业老板、外贸/本地生活/服务业负责人",
                offer="企业AI SOP诊断与试点搭建",
                score=96,
            )
        )

    solo = ROOT / "ai-solo-founder-douyin"
    narration = _read_text(solo / "narration.txt", 1000)
    solo_assets = _latest_files(solo, {".mp4", ".mp3", ".png", ".jpg"}, 8)
    if solo.exists():
        signals.append(
            ProjectSignal(
                key="solo_founder_build",
                name="一个人AI创业抖音成片项目",
                path=solo,
                status="已有竖屏视频工程、旁白、音频、帧图和MP4草稿",
                assets=solo_assets,
                insight=narration or "一个人也能用AI把代码、后台、客服、知识库、CRM和自动化流程组合成企业级系统。",
                audience="想用AI做企业服务的个人创业者、AI服务商、企业老板",
                offer="一人AI获客运营系统搭建",
                score=94,
            )
        )

    internal_growth = ROOT / "backend" / "internal_growth"
    if internal_growth.exists():
        signals.append(
            ProjectSignal(
                key="internal_growth_os",
                name="Internal Growth OS",
                path=internal_growth,
                status="已有需求雷达、内容工厂、发布审核、CRM跟进、销售分析和复盘数据结构",
                assets=[
                    "backend/internal_growth/workflows.py",
                    "backend/internal_growth/content_factory.py",
                    "docs/INTERNAL_GROWTH_OS.md",
                ],
                insight="抖音不是单纯发视频，而是用视频筛选高意向客户，再把私信、评论、表单沉淀进CRM。",
                audience="咨询服务、培训、知识付费、本地生活和AI服务团队",
                offer="内部获客运营系统：内容测试、线索跟进、销售复盘",
                score=93,
            )
        )

    desktop_agent = ROOT / "desktop_agent"
    listener = ROOT / "scripts" / "desktop_auto_reply_listener.py"
    if desktop_agent.exists() or listener.exists():
        signals.append(
            ProjectSignal(
                key="customer_reply_agent",
                name="桌面客服/多平台候选回复Agent",
                path=desktop_agent if desktop_agent.exists() else listener,
                status="已有微信、抖音、闲鱼等桌面客服候选回复能力，敏感外发停在人工确认",
                assets=["desktop_agent", "scripts/desktop_auto_reply_listener.py"],
                insight="AI客服最容易出问题的地方不是生成回复，而是没有风控、知识库引用和人工确认。",
                audience="咨询量大、客服重复答复多、怕自动回复翻车的商家",
                offer="AI客服话术、知识库、CRM和人工审核流程搭建",
                score=91,
            )
        )

    miniapp = ROOT / "douyin-miniapp"
    if miniapp.exists():
        signals.append(
            ProjectSignal(
                key="douyin_miniapp",
                name="抖音小程序/承接入口",
                path=miniapp,
                status="已有抖音小程序方向，可作为后续线索承接入口",
                assets=_latest_files(miniapp, {".md", ".json", ".ts", ".js"}, 5),
                insight="视频负责筛选需求，承接入口负责收集行业、预算、痛点和联系方式。",
                audience="从抖音进入咨询的企业客户",
                offer="抖音线索表单/小程序承接链路",
                score=86,
            )
        )

    material_factory = ROOT / "enterprise-material-factory"
    if material_factory.exists():
        signals.append(
            ProjectSignal(
                key="enterprise_material_factory",
                name="企业素材工厂",
                path=material_factory,
                status="适合做企业客户素材交付和案例包装",
                assets=_latest_files(material_factory, {".md", ".json", ".png", ".jpg"}, 5),
                insight="企业客户买的不是一条视频，而是一套能持续复用的素材和成交话术。",
                audience="需要持续做内容的企业客户",
                offer="企业短视频脚本、主图、详情页、客服话术素材工厂",
                score=84,
            )
        )

    return sorted(signals, key=lambda item: item.score, reverse=True)


def build_topics(signals: list[ProjectSignal]) -> list[Topic]:
    by_key = {signal.key: signal for signal in signals}
    topics: list[Topic] = []

    if "summit_ai_sop" in by_key:
        signal = by_key["summit_ai_sop"]
        topics.append(
            Topic(
                key="summit_ai_sop",
                source=signal.name,
                title="参加完AI企业峰会，我更确定一件事",
                hook="企业不是缺AI工具，企业缺的是能真正跑起来的AI SOP。",
                pain="老板关心的不是模型参数，而是能不能少招重复岗位、客户咨询能不能更快成交。",
                proof="峰会照片里反复出现的关键词是营销SOP、业务SOP、客户转化、内容运营和端到端工作台。",
                solution="用Agent把客服、知识库、CRM、内容获客和数据复盘串成一个试点流程。",
                cta="想看企业AI SOP怎么先做一个小试点，私信我发「Agent」。",
                assets=signal.assets,
                score=signal.score,
            )
        )

    if "internal_growth_os" in by_key:
        signal = by_key["internal_growth_os"]
        topics.append(
            Topic(
                key="douyin_is_filter",
                source=signal.name,
                title="抖音不是发视频，是筛选高意向客户",
                hook="真正的抖音获客，不是每天硬发，而是每条视频都在筛选一种客户需求。",
                pain="很多人视频发了几十条，却没有把评论、私信、咨询和跟进动作接进CRM。",
                proof="现有系统已经有需求雷达、内容草稿、发布审核和CRM跟进，只差真实数据回填闭环。",
                solution="每天只测一个痛点：视频讲清楚，私信接住，CRM跟进，第二天用数据决定继续还是换题。",
                cta="如果你也想把抖音内容变成获客系统，私信我发「获客」。",
                assets=signal.assets,
                score=signal.score,
            )
        )

    if "solo_founder_build" in by_key:
        signal = by_key["solo_founder_build"]
        topics.append(
            Topic(
                key="solo_ai_founder",
                source=signal.name,
                title="一个人做AI创业，先别急着卖工具",
                hook="我现在做的不是一个AI工具，而是一套能给企业交付结果的工作流。",
                pain="个人创业者最大的问题不是不会写代码，而是不知道先验证哪个需求、怎么持续获客。",
                proof="本地已经有竖屏成片、旁白、后台、数据和内容工厂，可以把进展拍成真实创业纪录片。",
                solution="用每天一条视频记录：今天发现什么需求、做了哪个模块、它能帮客户少做什么重复动作。",
                cta="想看我怎么一个人搭企业AI系统，私信我发「一人公司」。",
                assets=signal.assets,
                score=signal.score,
            )
        )

    if "customer_reply_agent" in by_key:
        signal = by_key["customer_reply_agent"]
        topics.append(
            Topic(
                key="ai_customer_service_guardrails",
                source=signal.name,
                title="AI客服不能只会自动回复",
                hook="AI客服真正值钱的地方，不是替你乱回消息，而是知道什么时候必须转人工。",
                pain="退款、投诉、付款、承诺、隐私这些场景，一旦自动乱发，客户体验和账号风险都会出问题。",
                proof="当前桌面Agent已经把候选回复、风控识别、知识库引用和人工确认分开处理。",
                solution="先做候选回复和CRM记录，等知识库和风控稳定后，再逐步开放低风险自动化。",
                cta="如果你的客服每天重复答同样问题，私信我发「客服」。",
                assets=signal.assets,
                score=signal.score,
            )
        )

    if "enterprise_material_factory" in by_key:
        signal = by_key["enterprise_material_factory"]
        topics.append(
            Topic(
                key="material_factory",
                source=signal.name,
                title="企业做短视频，缺的不是灵感，是素材工厂",
                hook="一条爆款不能解决企业获客，能复用的素材工厂才行。",
                pain="很多企业每次发视频都从零开始想标题、脚本、封面和客服话术，效率很低。",
                proof="现有项目已经能把商家需求拆成短视频、主图、详情图和客服话术。",
                solution="把每个客户痛点沉淀成脚本模板、封面模板、话术模板和复盘指标。",
                cta="想把企业内容生产变成流程，私信我发「素材」。",
                assets=signal.assets,
                score=signal.score,
            )
        )

    return sorted(topics, key=lambda item: item.score, reverse=True)


def select_topics(topics: list[Topic], date: datetime, limit: int) -> list[Topic]:
    if not topics:
        return []
    offset = (date.timetuple().tm_yday - 1) % len(topics)
    rotated = topics[offset:] + topics[:offset]
    return rotated[:limit]


def build_douyin_payload(topic: Topic, date: datetime) -> dict[str, Any]:
    date_label = date.strftime("%Y-%m-%d")
    script_15s = (
        f"{topic.hook} {topic.pain} 我今天用一个小试点验证：{topic.solution} "
        f"{topic.cta}"
    )
    script_30s = (
        f"{topic.hook}\n\n"
        f"这条内容要击中的痛点是：{topic.pain}\n\n"
        f"我今天看的证据是：{topic.proof}\n\n"
        f"所以我的做法不是先卖一个大系统，而是先做一个能跑起来的小试点：{topic.solution}\n\n"
        f"{topic.cta}"
    )
    script_60s = (
        f"我今天继续扫描自己的项目目录，发现一个很适合做抖音获客的主题：{topic.title}。\n\n"
        f"{topic.hook}\n\n"
        f"企业客户真正焦虑的是：{topic.pain}\n\n"
        f"这不是凭空想的，项目证据是：{topic.proof}\n\n"
        f"所以这条视频不讲概念，只讲一个结果：{topic.solution}\n\n"
        "如果有人咨询，就进入CRM跟进；没有咨询，明天换一个痛点继续测。"
        f"{topic.cta}"
    )
    storyboard = [
        {
            "time": "0-3s",
            "visual": "峰会照片、项目目录或成片画面快速切入",
            "subtitle": topic.hook,
            "purpose": "强钩子，先抛反常识结论",
        },
        {
            "time": "3-10s",
            "visual": "切到项目文件、后台页面或手写关键词",
            "subtitle": topic.pain,
            "purpose": "说清楚企业客户痛点",
        },
        {
            "time": "10-24s",
            "visual": "展示Agent流程：需求 -> 内容 -> 发布审核 -> CRM -> 复盘",
            "subtitle": topic.solution,
            "purpose": "给出可交付方法",
        },
        {
            "time": "24-36s",
            "visual": "展示素材/成片/后台草稿队列",
            "subtitle": topic.proof,
            "purpose": "用真实进展提高可信度",
        },
        {
            "time": "36-45s",
            "visual": "黑底大字封面式收束，显示私信关键词",
            "subtitle": topic.cta,
            "purpose": "引导高意向客户私信",
        },
    ]
    return {
        "daily_key": f"douyin-daily:{date_label}:{topic.key}",
        "source": topic.source,
        "source_key": topic.key,
        "title": topic.title,
        "cover_copy": topic.hook,
        "script_15s": script_15s,
        "script_30s": script_30s,
        "script_60s": script_60s,
        "storyboard": storyboard,
        "subtitles": [
            topic.hook,
            topic.pain,
            topic.solution,
            topic.cta,
        ],
        "caption": (
            f"{topic.hook}\n\n"
            f"{topic.solution}\n\n"
            f"{topic.cta}\n\n"
            "#AI创业 #抖音获客 #企业AI #AI客服 #CRM #自动化流程 #一人公司"
        ),
        "hashtags": ["AI创业", "抖音获客", "企业AI", "AI客服", "CRM", "自动化流程", "一人公司"],
        "assets": topic.assets,
        "render_plan": {
            "format": "9:16 vertical",
            "duration_seconds": 45,
            "style": "真实创业纪录片 + 项目后台录屏 + 黑色玻璃UI字幕",
            "preferred_tool": "HyperFrames or Remotion",
            "output_target": f"output/douyin-daily/{date.strftime('%Y%m%d')}/video_{topic.key}.mp4",
        },
        "publish_review": {
            "status": "review",
            "human_confirmation_required": True,
            "rules": [
                "不要承诺全自动成交",
                "不要自动私信陌生客户",
                "发布前检查案例和素材是否可公开",
                "发布后2小时、24小时、72小时回填播放、收藏、评论、私信和成交",
            ],
        },
        "comment_reply_seed": [
            "可以，先从一个具体流程做试点，比如客服、线索跟进或内容获客。",
            "我建议先看行业、咨询量和重复问题，再决定用AI接哪一段。",
            "不建议一上来全自动，先做候选回复和人工确认更稳。",
        ],
    }


def find_or_create_demand(topic: Topic) -> DemandSignal:
    marker = f"douyin_project_scan:{topic.key}"
    for demand in store.list_demands():
        if demand.source_detail == marker:
            return demand
    demand = DemandSignal(
        id=str(uuid.uuid4()),
        name=topic.title,
        source_type="manual",
        source_detail=marker,
        industry="企业AI / 抖音获客 / AI服务",
        keywords=["抖音获客", "短视频", "AI客服", "CRM", "SOP", "自动化"],
        pain_points=topic.pain,
        raw_text=f"{topic.hook}\n{topic.proof}\n{topic.solution}",
        buying_possibility=min(95, max(60, topic.score)),
        recommended_action="生成抖音视频草稿，进入人工审核发布队列，并在发布后回填数据。",
    )
    return store.save_demand(demand)


def upsert_content_and_publish(payload: dict[str, Any], demand: DemandSignal) -> tuple[ContentTask, PublishingRecord]:
    daily_key = str(payload["daily_key"])
    existing_tasks = [
        item
        for item in store.list_content_tasks()
        if item.platform == "douyin" and item.payload.get("daily_key") == daily_key
    ]
    if existing_tasks:
        task = existing_tasks[0]
        task.payload = payload
        task.title = str(payload["title"])
        task.updated_at = now_iso()
        task = store.save_content_task(task)
    else:
        task = store.save_content_task(
            ContentTask(
                id=str(uuid.uuid4()),
                demand_id=demand.id,
                opportunity_id="",
                platform="douyin",
                status="draft",
                title=str(payload["title"]),
                payload=payload,
                review_note="由 douyin_daily_growth_runner.py 扫描本地项目后生成，发布前需要人工审核。",
            )
        )

    existing_records = [
        item
        for item in store.list_publishing_records()
        if item.content_task_id == task.id and item.platform == "douyin"
    ]
    if existing_records:
        record = existing_records[0]
        record.status = "review"
        record.notes = "Project scan content pack ready. Human confirmation required before Douyin publishing."
        record.updated_at = now_iso()
        record = store.save_publishing_record(record)
    else:
        record = store.save_publishing_record(
            PublishingRecord(
                id=str(uuid.uuid4()),
                content_task_id=task.id,
                platform="douyin",
                status="review",
                notes="Project scan content pack ready. Human confirmation required before Douyin publishing.",
            )
        )
    return task, record


def write_pack(date: datetime, signals: list[ProjectSignal], payloads: list[dict[str, Any]], saved: list[dict[str, str]]) -> Path:
    pack_dir = PACK_ROOT / date.strftime("%Y%m%d")
    pack_dir.mkdir(parents=True, exist_ok=True)
    json_path = pack_dir / f"douyin_daily_pack_{date.strftime('%Y%m%d')}.json"
    md_path = pack_dir / f"douyin_daily_pack_{date.strftime('%Y%m%d')}.md"

    data = {
        "date": date.strftime("%Y-%m-%d"),
        "workspace": str(ROOT),
        "project_signals": [
            {
                "key": signal.key,
                "name": signal.name,
                "path": str(signal.path),
                "status": signal.status,
                "insight": signal.insight,
                "audience": signal.audience,
                "offer": signal.offer,
                "assets": signal.assets,
                "score": signal.score,
            }
            for signal in signals
        ],
        "douyin_payloads": payloads,
        "saved_records": saved,
        "automation_boundary": [
            "脚本会自动扫描、自动生成内容包、自动进入审核队列。",
            "抖音上传和最终发布必须使用官方授权能力或人工确认。",
            "评论、私信、交易、退款、承诺类动作不做无人值守自动化。",
        ],
    }
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    lines: list[str] = [
        f"# 抖音日更获客内容包 - {date.strftime('%Y-%m-%d')}",
        "",
        "## 今日扫描到的项目资产",
        "",
    ]
    for signal in signals:
        lines.extend(
            [
                f"### {signal.name}",
                f"- 路径：`{signal.path}`",
                f"- 状态：{signal.status}",
                f"- 可转化观点：{signal.insight}",
                f"- 目标客户：{signal.audience}",
                f"- 可卖服务：{signal.offer}",
                "",
            ]
        )

    lines.extend(["## 今日优先发布内容", ""])
    for index, payload in enumerate(payloads, start=1):
        lines.extend(
            [
                f"### {index}. {payload['title']}",
                f"- 来源：{payload['source']}",
                f"- 封面字：{payload['cover_copy']}",
                f"- 私信引导：{payload['subtitles'][-1]}",
                "",
                "#### 30秒口播",
                "",
                str(payload["script_30s"]),
                "",
                "#### 分镜",
                "",
            ]
        )
        for shot in payload["storyboard"]:
            lines.append(f"- {shot['time']}：{shot['visual']}｜字幕：{shot['subtitle']}")
        lines.extend(
            [
                "",
                "#### 发布文案",
                "",
                str(payload["caption"]),
                "",
                "#### 审核边界",
                "",
            ]
        )
        for rule in payload["publish_review"]["rules"]:
            lines.append(f"- {rule}")
        lines.append("")

    lines.extend(
        [
            "## 自动化边界",
            "",
            "- 自动：扫描项目、生成选题、脚本、分镜、封面、文案、发布审核记录。",
            "- 半自动：可打开发布面板或官方发布工具，由人确认上传/发布。",
            "- 禁止无人值守：自动私信陌生客户、自动群发、自动承诺成交、自动处理交易/退款。",
            "",
            "## 数据回填",
            "",
            "- 发布后 2 小时：回填播放、完播感受、评论问题。",
            "- 发布后 24 小时：回填收藏、私信、表单、有效咨询。",
            "- 发布后 72 小时：回填成交进展，并决定这个主题继续做、改标题、还是停止。",
            "",
        ]
    )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan local projects and create a daily Douyin acquisition content pack.")
    parser.add_argument("--date", default="", help="Date in YYYY-MM-DD. Defaults to Asia/Shanghai today.")
    parser.add_argument("--limit", type=int, default=1, help="How many Douyin drafts to create for today.")
    parser.add_argument("--no-store", action="store_true", help="Only write output pack; do not update internal_growth data.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    date = datetime.now(TZ) if not args.date else datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=TZ)
    signals = scan_project_signals()
    topics = build_topics(signals)
    selected = select_topics(topics, date, max(1, args.limit))
    if not selected:
        print("No project signals found.")
        return 1

    payloads = [build_douyin_payload(topic, date) for topic in selected]
    saved: list[dict[str, str]] = []
    if not args.no_store:
        for topic, payload in zip(selected, payloads):
            demand = find_or_create_demand(topic)
            task, record = upsert_content_and_publish(payload, demand)
            saved.append(
                {
                    "topic": topic.key,
                    "demand_id": demand.id,
                    "content_task_id": task.id,
                    "publishing_record_id": record.id,
                    "publishing_status": record.status,
                }
            )

    md_path = write_pack(date, signals, payloads, saved)
    print(
        json.dumps(
            {
                "date": date.strftime("%Y-%m-%d"),
                "signals": len(signals),
                "drafts": len(payloads),
                "pack": str(md_path),
                "saved": saved,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
