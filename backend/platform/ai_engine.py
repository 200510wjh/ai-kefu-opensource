from __future__ import annotations

import base64
import json
import os
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class AIEngineConfig(BaseModel):
    provider: str = "openai_compatible"
    api_key: str = ""
    model: str = ""
    base_url: str = "https://api.openai.com/v1"
    temperature: float = 0.7
    timeout: float = 45


class ImageEngineConfig(BaseModel):
    provider: str = "openai_compatible"
    api_key: str = ""
    model: str = ""
    base_url: str = "https://api.openai.com/v1"
    size: str = "1024x1024"
    timeout: float = 80
    response_format: str = ""
    quality: str = ""


class AIMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionResult(BaseModel):
    content: str
    raw: dict[str, Any] = Field(default_factory=dict)


class ImageGenerationResult(BaseModel):
    prompt: str
    provider: str
    model: str = ""
    image_url: str | None = None
    artifact_url: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class RiskAssessmentResult(BaseModel):
    risk_flags: list[str] = Field(default_factory=list)
    need_followup: bool = False


class IntentScoreResult(BaseModel):
    score: int
    reasons: list[str] = Field(default_factory=list)


class ConversationSummaryResult(BaseModel):
    summary: str
    next_action: str = ""


class AITextResult(BaseModel):
    text: str
    mode: Literal["ai", "rule"] = "rule"
    raw: dict[str, Any] = Field(default_factory=dict)


class AIEngine:
    """Single gateway for model-backed capabilities.

    Business modules must not call provider HTTP APIs directly. They should ask
    this engine for text, JSON, image prompts, scoring, summaries, or later
    specialized decisions. This class intentionally keeps provider mechanics
    small and boring so old code can migrate without changing public APIs.
    """

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or Path(os.getenv("MERCHANT_AUTO_CUT_DATA_DIR", "data"))

    @staticmethod
    def normalize_base_url(base_url: str) -> str:
        base = (base_url or "https://api.openai.com/v1").rstrip("/")
        return base if base.endswith("/v1") else f"{base}/v1"

    def chat_config(self, temperature: float | None = None, timeout: float | None = None) -> AIEngineConfig:
        return AIEngineConfig(
            provider=os.getenv("AI_PROVIDER", "openai_compatible"),
            api_key=os.getenv("AI_API_KEY") or os.getenv("OPENAI_API_KEY") or "",
            model=os.getenv("AI_MODEL", ""),
            base_url=self.normalize_base_url(os.getenv("AI_BASE_URL", "https://api.openai.com/v1")),
            temperature=float(temperature if temperature is not None else os.getenv("AI_TEMPERATURE", "0.7")),
            timeout=float(timeout if timeout is not None else os.getenv("AI_TIMEOUT", "45")),
        )

    def image_config(self) -> ImageEngineConfig:
        base_url = os.getenv("IMAGE_BASE_URL") or os.getenv("AI_BASE_URL", "https://api.openai.com/v1")
        return ImageEngineConfig(
            provider=os.getenv("IMAGE_PROVIDER", "openai_compatible"),
            api_key=os.getenv("IMAGE_API_KEY") or os.getenv("AI_API_KEY") or os.getenv("OPENAI_API_KEY") or "",
            model=os.getenv("IMAGE_MODEL", ""),
            base_url=self.normalize_base_url(base_url),
            size=os.getenv("IMAGE_SIZE", "1024x1024"),
            timeout=float(os.getenv("IMAGE_TIMEOUT", "80")),
            response_format=os.getenv("IMAGE_RESPONSE_FORMAT", ""),
            quality=os.getenv("IMAGE_QUALITY", ""),
        )

    def is_chat_configured(self) -> bool:
        config = self.chat_config()
        return bool(config.api_key and config.model)

    def complete_chat(
        self,
        messages: list[dict[str, str]] | list[AIMessage],
        *,
        temperature: float | None = None,
        timeout: float | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> ChatCompletionResult:
        config = self.chat_config(temperature=temperature, timeout=timeout)
        if not config.api_key or not config.model:
            raise RuntimeError("AI provider is not configured")

        normalized_messages = [
            item.model_dump() if isinstance(item, AIMessage) else {"role": item["role"], "content": item["content"]}
            for item in messages
        ]
        body: dict[str, Any] = {
            "model": config.model,
            "messages": normalized_messages,
            "temperature": config.temperature,
        }
        if response_format:
            body["response_format"] = response_format

        request = urllib.request.Request(
            f"{config.base_url}/chat/completions",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=config.timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        return ChatCompletionResult(content=str(data["choices"][0]["message"]["content"]).strip(), raw=data)

    def complete_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        history: list[dict[str, str]] | None = None,
        temperature: float | None = None,
        timeout: float | None = None,
    ) -> str:
        messages = [{"role": "system", "content": system_prompt}, *(history or []), {"role": "user", "content": user_prompt}]
        return self.complete_chat(messages, temperature=temperature, timeout=timeout).content

    def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        result = self.complete_chat(
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            temperature=temperature,
            timeout=timeout,
            response_format={"type": "json_object"},
        )
        return parse_json_object(result.content)

    def assess_risk(self, text: str) -> RiskAssessmentResult:
        groups = {
            "退款/售后": ["退款", "退钱", "退货", "不满意", "售后", "赔付"],
            "投诉/差评": ["投诉", "差评", "骗人", "骗子", "举报", "维权", "假货"],
            "付款/资金": ["付款", "转账", "银行卡", "收款", "支付", "扣款", "账单"],
            "账号/权限": ["账号", "密码", "验证码", "登录", "封号", "权限"],
            "隐私信息": ["手机号", "电话", "地址", "身份证", "隐私", "个人信息"],
            "发票/合同": ["发票", "合同", "协议", "公章"],
        }
        lowered = text.lower()
        flags = [label for label, terms in groups.items() if any(term.lower() in lowered for term in terms)]
        return RiskAssessmentResult(risk_flags=flags, need_followup=bool(flags))

    def score_intent(self, text: str) -> IntentScoreResult:
        score = 35
        reasons: list[str] = []
        term_groups = [
            ("价格/购买", ["多少钱", "价格", "报价", "收费", "费用", "套餐", "试用", "购买", "合作"], 8),
            ("联系方式/预约", ["电话", "微信", "预约", "演示", "发我", "联系"], 8),
            ("接入/部署", ["接入", "官网", "网站", "网页", "代码", "气泡", "api", "部署"], 6),
            ("客服/线索", ["客服", "自动回复", "知识库", "会话", "线索", "crm"], 5),
        ]
        lowered = text.lower()
        for label, terms, weight in term_groups:
            hits = [term for term in terms if term.lower() in lowered]
            if hits:
                score += weight * min(len(hits), 3)
                reasons.append(label)
        risk = self.assess_risk(text)
        if risk.risk_flags:
            score += 12
            reasons.append("风险跟进")
        return IntentScoreResult(score=min(score, 95), reasons=reasons)

    def generate_reply(
        self,
        *,
        system_prompt: str,
        user_message: str,
        history: list[dict[str, str]] | None = None,
        fallback_text: str = "",
        temperature: float | None = None,
        timeout: float | None = None,
    ) -> AITextResult:
        if not self.is_chat_configured():
            return AITextResult(text=fallback_text, mode="rule")
        text = self.complete_text(
            system_prompt=system_prompt,
            user_prompt=user_message,
            history=history,
            temperature=temperature,
            timeout=timeout,
        )
        return AITextResult(text=text, mode="ai")

    def summarize_conversation(self, messages: list[dict[str, str]]) -> ConversationSummaryResult:
        transcript = "\n".join(f"{item.get('role', 'unknown')}: {item.get('content', '')}" for item in messages[-20:])
        if not transcript.strip():
            return ConversationSummaryResult(summary="暂无可总结的会话。", next_action="等待客户发送消息。")
        if not self.is_chat_configured():
            last = messages[-1].get("content", "") if messages else ""
            return ConversationSummaryResult(summary=f"最近一轮：{last[:120]}", next_action="人工查看最近消息并决定是否跟进。")
        parsed = self.complete_json(
            system_prompt="你是企业客服主管，只输出 JSON。",
            user_prompt=(
                "请总结这段客户会话，输出 JSON："
                '{"summary":"一句话总结客户需求","next_action":"建议下一步动作"}\n'
                f"{transcript}"
            ),
            temperature=0.35,
            timeout=30,
        )
        return ConversationSummaryResult(
            summary=str(parsed.get("summary", "")).strip() or "暂无总结。",
            next_action=str(parsed.get("next_action", "")).strip(),
        )

    def generate_script(self, context: dict[str, Any]) -> dict[str, Any]:
        if not self.is_chat_configured():
            return {
                "title": "企业客服成交脚本",
                "opening": "您好，我先确认一下您的业务场景，再给您推荐合适的接入方案。",
                "steps": [
                    {"title": "确认场景", "message": "您主要想先接官网客服，还是先解决微信/抖音这类私信回复？", "goal": "确认优先渠道"},
                    {"title": "说明方案", "message": "我们可以先导入 FAQ 和商品资料，让 AI 按企业资料回复并记录线索。", "goal": "建立可落地预期"},
                    {"title": "推进下一步", "message": "您发我行业、网站和 5 条常见问题，我先帮您跑一个测试场景。", "goal": "推动试用"},
                ],
                "objection_replies": [],
                "closing": "先跑小场景，看到真实会话和线索沉淀后再扩渠道。",
            }
        return self.complete_json(
            system_prompt="你是企业 AI 客服产品的成交脚本专家，只输出 JSON。",
            user_prompt=(
                "基于以下上下文生成客服脚本 JSON，字段：title, opening, steps, objection_replies, closing。"
                "steps 和 objection_replies 中每项必须有 title/message/goal。\n"
                f"{json.dumps(context, ensure_ascii=False)}"
            ),
            temperature=0.72,
            timeout=35,
        )

    def generate_product_copy(self, context: dict[str, Any]) -> dict[str, Any]:
        if not self.is_chat_configured():
            product_name = str(context.get("product_name") or "商品")
            selling_points = context.get("selling_points") or []
            if isinstance(selling_points, str):
                selling_points = [item.strip() for item in selling_points.split(",") if item.strip()]
            return {
                "title": f"{product_name} 企业电商上架文案",
                "short_title": product_name[:20],
                "selling_points": selling_points[:6],
                "detail_sections": ["核心卖点", "使用场景", "规格参数", "售后说明"],
                "customer_faq": [{"question": "适合什么人？", "answer": "建议结合商品资料和目标人群确认。"}],
            }
        return self.complete_json(
            system_prompt="你是企业电商商品运营专家，只输出 JSON。",
            user_prompt=(
                "生成商品上架文案 JSON，字段：title, short_title, selling_points, detail_sections, customer_faq。"
                f"\n{json.dumps(context, ensure_ascii=False)}"
            ),
            temperature=0.68,
            timeout=35,
        )

    def generate_prompt(self, context: dict[str, Any]) -> dict[str, Any]:
        if not self.is_chat_configured():
            subject = str(context.get("subject") or context.get("product_name") or "商品")
            style = str(context.get("style") or "高级电商科技风")
            return {
                "prompt": f"{subject}，{style}，清晰主体，适合电商主图和详情图，真实产品质感，商业摄影光影。",
                "negative_prompt": "低清晰度，文字乱码，变形，过度夸张，侵权 logo",
            }
        return self.complete_json(
            system_prompt="你是商业图片和视频生成 Prompt 工程师，只输出 JSON。",
            user_prompt=(
                "生成可用于图片/视频模型的 Prompt JSON，字段：prompt, negative_prompt。"
                f"\n{json.dumps(context, ensure_ascii=False)}"
            ),
            temperature=0.65,
            timeout=30,
        )

    def generate_image(self, prompt: str) -> ImageGenerationResult:
        config = self.image_config()
        if not config.api_key:
            raise RuntimeError("Image provider is not configured")

        body: dict[str, Any] = {"prompt": prompt, "size": config.size, "n": 1}
        if config.model:
            body["model"] = config.model
        if config.quality:
            body["quality"] = config.quality
        if config.response_format:
            body["response_format"] = config.response_format

        request = urllib.request.Request(
            f"{config.base_url}/images/generations",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=config.timeout) as response:
            data = json.loads(response.read().decode("utf-8"))

        first = (data.get("data") or [{}])[0]
        artifact_url = None
        if first.get("b64_json"):
            artifact_url = self.save_b64_image(str(first["b64_json"]))
        return ImageGenerationResult(
            prompt=prompt,
            provider=config.provider,
            model=config.model,
            image_url=first.get("url"),
            artifact_url=artifact_url,
            raw=data,
        )

    def save_b64_image(self, raw: str) -> str:
        artifact_dir = self.data_dir / "artifacts" / "images"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{uuid.uuid4()}.png"
        (artifact_dir / filename).write_bytes(base64.b64decode(raw))
        return f"/artifacts/images/{filename}"


def parse_json_object(content: str) -> dict[str, Any]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.removeprefix("json").strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        cleaned = cleaned[start : end + 1]
    return json.loads(cleaned)


def default_ai_engine(data_dir: Path | None = None) -> AIEngine:
    return AIEngine(data_dir=data_dir)
