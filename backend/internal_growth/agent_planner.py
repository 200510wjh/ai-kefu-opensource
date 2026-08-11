from __future__ import annotations

import uuid

from backend.internal_growth.models import AgentPlan, AgentPlanRequest


CONTACT_TERMS = ["联系", "触达", "私信", "电话", "官网表单"]
WORKFLOW_TERMS = ["workflow", "流程", "今日获客", "运行"]
PROSPECT_SEARCH_TERMS = ["找客户", "找线索", "找潜在客户", "搜索", "抓取", "采集", "抖音", "百度", "闲鱼", "小红书", "快手"]
PROSPECT_ACTION_TERMS = ["找", "搜索", "抓取", "采集"]
SUMMIT_CONTENT_TERMS = ["峰会", "大会", "会议", "照片", "PPT", "ppt", "素材", "内容包"]
CONTENT_ACTION_TERMS = ["发抖音", "做视频", "视频", "脚本", "选题", "内容", "个人IP", "ip"]
XIANYU_DRAFT_TERMS = ["闲鱼", "咸鱼"]
XIANYU_DRAFT_ACTION_TERMS = ["发闲鱼", "发咸鱼", "闲鱼发布", "咸鱼发布", "发布闲鱼", "发布咸鱼", "上架", "商品", "服务", "草稿"]
OPEN_SOURCE_TERMS = ["github", "GitHub", "开源", "插件", "优质项目", "项目选型"]
NEGATED_AUTO_TERMS = ["不要自动发送", "不自动发送", "不要自动私信", "不自动私信", "只生成", "人工发送"]
AUTO_CONTACT_TERMS = ["自动发送", "自动私信", "自动提交", "自动打电话"]


def plan_agent_task(payload: AgentPlanRequest) -> AgentPlan:
    task = payload.task.strip()
    lowered = task.lower()
    needs_contact = any(term in task for term in CONTACT_TERMS)
    needs_workflow = any(term in lowered for term in WORKFLOW_TERMS)
    needs_open_source = any(term in task for term in OPEN_SOURCE_TERMS)
    has_prospect_source = any(term in task for term in PROSPECT_SEARCH_TERMS)
    looks_like_customer_search = any(term in task for term in ["客户", "线索", "潜在客户", "公开客户", "真实客户"])
    needs_prospect_search = has_prospect_source and any(term in task for term in PROSPECT_ACTION_TERMS) and (not needs_open_source or looks_like_customer_search)
    needs_summit_content = any(term in task for term in SUMMIT_CONTENT_TERMS) and any(term in task for term in CONTENT_ACTION_TERMS)
    needs_xianyu_draft = any(term in task for term in XIANYU_DRAFT_TERMS) and any(term in task for term in XIANYU_DRAFT_ACTION_TERMS)
    needed_tools: list[str] = []
    steps: list[str] = []
    expected: list[str] = []
    requires_human = False

    if needs_prospect_search:
        needed_tools.append("create_public_prospect_search")
        steps.extend(["明确行业、平台和痛点关键词", "生成公开平台搜索入口", "等待人工打开平台并粘贴公开证据"])
        expected.extend(["平台搜索链接", "采集边界", "候选客户入库入口"])
    if needs_summit_content:
        needed_tools.append("generate_summit_content_pack")
        steps.extend(["读取峰会主题和素材线索", "生成抖音/闲鱼/朋友圈内容草稿", "创建发布审核记录"])
        expected.extend(["抖音脚本", "闲鱼服务草稿", "朋友圈复盘", "发布审核队列"])
    if needs_xianyu_draft and "create_xianyu_service_draft" not in needed_tools:
        needed_tools.append("create_xianyu_service_draft")
        steps.extend(["生成闲鱼服务商品标题和详情", "写明交付边界", "进入人工审核发布队列"])
        expected.extend(["闲鱼服务商品草稿", "发布审核记录"])
    if needs_open_source:
        needed_tools.append("recommend_open_source_stack")
        steps.extend(["按目标筛选GitHub开源项目", "标注采用优先级和风险边界", "只输出接入建议不执行第三方代码"])
        expected.extend(["开源项目推荐清单", "接入顺序", "风险边界"])
    if needs_contact:
        needed_tools.append("generate_contact_suggestion")
        steps.extend(["读取 CRM 线索", "生成触达理由和人工发送草稿", "创建人工跟进任务"])
        expected.extend(["触达理由", "私信草稿", "电话开场白", "官网表单留言"])
        has_auto_contact = any(term in task for term in AUTO_CONTACT_TERMS)
        has_negated_auto_contact = any(term in task for term in NEGATED_AUTO_TERMS)
        if has_auto_contact and not has_negated_auto_contact:
            needed_tools.append("auto_contact_customer")
            requires_human = True
    if needs_workflow:
        needed_tools.append("run_daily_growth_workflow")
        steps.append("运行今日获客流程并停在人工审核")
        expected.append("Workflow 运行结果")
    if not needed_tools:
        needed_tools.append("generate_contact_suggestion")
        steps.extend(["默认按真实客户人工触达准备处理", "只生成建议，不执行外部联系"])
        expected.append("人工触达建议")

    return AgentPlan(
        id=str(uuid.uuid4()),
        task_goal=task,
        needed_tools=needed_tools,
        execution_steps=steps,
        risk_assessment="包含外部联系意图时必须人工确认；v1 不允许自动私信、自动提交表单或自动外呼。",
        requires_human_confirmation=requires_human,
        expected_outputs=expected,
    )
