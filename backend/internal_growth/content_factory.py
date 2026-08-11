from __future__ import annotations

import json
import uuid

from backend.internal_growth.models import (
    ContentPlatform,
    ContentTask,
    DemandSignal,
    DouyinContent,
    MomentsContent,
    OpportunityScore,
    XianyuContent,
)
from backend.platform.ai_engine import default_ai_engine


def fallback_douyin(demand: DemandSignal) -> DouyinContent:
    pain = demand.pain_points.strip()
    industry = demand.industry or "老板"
    return DouyinContent(
        title=f"{industry}别再硬找客户了，先测试这个需求",
        script_15s=f"客户不是不买，是你每天都在猜需求。今天发现一个痛点：{pain[:80]}。先用一条内容测试咨询量，再决定要不要做交付。",
        script_30s=(
            f"最近看到一个真实需求：{demand.name}。客户痛点不是想听AI多厉害，而是{pain[:120]}。"
            "我的做法是先拆成一个低成本测试：一条内容、一个咨询入口、一个跟进动作。有人问，再做方案。没人问，立刻换方向。"
        ),
        script_60s=(
            f"如果你也在找客户，别先做产品，先看需求信号。今天这个方向是：{demand.name}。"
            f"典型痛点是：{pain[:180]}。我会先做三件事：第一，把痛点讲成人话；第二，给出一个能落地的结果；"
            "第三，把咨询客户沉淀到CRM里，第二天继续跟进。这样AI不是噱头，而是帮你减少无效试错。"
        ),
        storyboard=[
            "开头：展示客户痛点原话或需求关键词",
            "中段：拆解痛点、解决方案、实际结果",
            "结尾：引导咨询，强调人工确认方案",
        ],
        subtitles=["别先卖AI，先验证需求", "痛点要具体，方案要能交付", "有人咨询，再进入CRM跟进"],
        cover_copy=f"{demand.name}值得测吗？",
    )


def fallback_xianyu(demand: DemandSignal) -> XianyuContent:
    industry = demand.industry or "本地商家/个人业务/小团队"
    return XianyuContent(
        product_title=f"{demand.name} 需求诊断与获客内容方案",
        product_description=(
            f"适合行业：{industry}。\n"
            f"解决痛点：{demand.pain_points}\n"
            "交付内容：需求分析、内容脚本、咨询承接话术、跟进建议。先人工确认需求，再给具体方案。"
        ),
        main_image_copy=f"不是卖AI，是帮你把「{demand.name}」变成可测试获客动作",
        detail_image_copy=[
            "1. 先看客户痛点，不空喊AI",
            "2. 输出短视频/闲鱼/朋友圈三类内容",
            "3. 有咨询后给跟进策略和CRM沉淀",
        ],
    )


def fallback_moments(demand: DemandSignal) -> MomentsContent:
    return MomentsContent(
        case_post=(
            f"今天复盘一个需求方向：{demand.name}。\n\n"
            f"客户真正卡住的是：{demand.pain_points}\n\n"
            "我现在不会一上来就做完整产品，而是先用内容测试：讲清痛点、给出方案、看有没有咨询。"
            "如果有咨询，再进入CRM跟进和报价。这样每天能少做很多无效判断。"
        ),
        sales_copy=(
            f"如果你也有类似「{demand.name}」的问题，可以把行业和现状发我。"
            "我先帮你判断这个需求值不值得做内容测试，再决定是否需要方案。"
        ),
    )


def generate_content_payload(demand: DemandSignal) -> dict[str, object]:
    engine = default_ai_engine()
    if not engine.is_chat_configured():
        return {
            "douyin": fallback_douyin(demand).model_dump(),
            "xianyu": fallback_xianyu(demand).model_dump(),
            "wechat_moments": fallback_moments(demand).model_dump(),
        }
    try:
        return engine.complete_json(
            system_prompt="你是内部获客运营系统的内容智能体，只输出JSON。内容必须围绕客户痛点、解决方案、实际结果，禁止空泛宣传AI。",
            user_prompt=(
                "基于这个市场需求生成抖音、闲鱼、朋友圈内容。JSON字段："
                "douyin(title,script_15s,script_30s,script_60s,storyboard,subtitles,cover_copy),"
                "xianyu(product_title,product_description,main_image_copy,detail_image_copy),"
                "wechat_moments(case_post,sales_copy)。\n"
                f"{demand.model_dump_json()}"
            ),
            temperature=0.72,
            timeout=45,
        )
    except Exception:
        return {
            "douyin": fallback_douyin(demand).model_dump(),
            "xianyu": fallback_xianyu(demand).model_dump(),
            "wechat_moments": fallback_moments(demand).model_dump(),
        }


def create_content_tasks(demand: DemandSignal, opportunity: OpportunityScore | None, platforms: list[ContentPlatform]) -> list[ContentTask]:
    payload = generate_content_payload(demand)
    tasks: list[ContentTask] = []
    for platform in platforms:
        platform_payload = payload.get(platform) or {}
        title = str(
            (platform_payload.get("title") if isinstance(platform_payload, dict) else "")
            or (platform_payload.get("product_title") if isinstance(platform_payload, dict) else "")
            or demand.name
        )
        tasks.append(
            ContentTask(
                id=str(uuid.uuid4()),
                demand_id=demand.id,
                opportunity_id=opportunity.id if opportunity else "",
                platform=platform,
                title=title,
                payload=json.loads(json.dumps(platform_payload, ensure_ascii=False)),
            )
        )
    return tasks
