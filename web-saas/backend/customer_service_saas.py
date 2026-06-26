from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
import urllib.error
import urllib.request
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field


router = APIRouter(prefix="/api", tags=["customer-service-saas"])

DATA_DIR = Path(os.getenv("MERCHANT_AUTO_CUT_DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
SQLITE_PATH = Path(os.getenv("CS_SQLITE_PATH", str(DATA_DIR / "customer_service.sqlite3")))
SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)


class FAQItem(BaseModel):
    question: str = ""
    answer: str = ""


class MerchantProfile(BaseModel):
    id: int | None = None
    username: str = ""
    merchant_code: str = ""
    business_name: str = ""
    industry: str = "通用服务"
    business_intro: str = ""
    products_services: str = ""
    pricing: str = ""
    promotions: str = ""
    hours: str = ""
    contact: str = ""
    faq: list[FAQItem] = []
    prompt_template: str = ""
    welcome_message: str = "您好，我是 AI 客服。请问有什么可以帮您？"


class AuthLoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class AuthLoginResponse(BaseModel):
    token: str
    merchant: MerchantProfile


class DashboardOverview(BaseModel):
    today_conversations: int
    auto_replies: int
    leads: int
    handoff_needed: int
    ai_mode: str
    knowledge_items: int = 0
    enabled_channels: int = 0


class WidgetSessionRequest(BaseModel):
    merchant_code: str = Field(min_length=1)
    visitor_id: str | None = None
    page_url: str = ""
    user_agent: str = ""


class WidgetSessionResponse(BaseModel):
    session_id: str
    visitor_id: str
    merchant_code: str
    welcome_message: str
    business_name: str


class WidgetMessageRequest(BaseModel):
    merchant_code: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    visitor_id: str | None = None
    message: str = Field(min_length=1, max_length=2000)
    page_url: str = ""


class WidgetMessageResponse(BaseModel):
    session_id: str
    customer_message: str
    ai_reply: str
    intent_score: int
    need_followup: bool
    risk_flags: list[str]


class ConversationSummary(BaseModel):
    session_id: str
    customer_id: int | None = None
    visitor_name: str
    last_query: str
    last_response: str
    intent_score: int
    need_followup: bool
    message_count: int
    updated_at: str


class ConversationDetail(BaseModel):
    session_id: str
    messages: list[dict[str, Any]]


class HandoffResponse(BaseModel):
    session_id: str
    need_followup: bool


class ChannelConfig(BaseModel):
    channel: str
    display_name: str
    mode: str = "assist"
    status: str = "draft"
    official_api_url: str = ""
    webhook_url: str = ""
    auto_reply_enabled: bool = False
    handoff_required: bool = True
    notes: str = ""


class ChannelConfigUpdate(BaseModel):
    display_name: str = ""
    mode: Literal["assist", "official_api", "manual"] = "assist"
    status: Literal["draft", "ready", "connected", "blocked"] = "draft"
    official_api_url: str = ""
    webhook_url: str = ""
    auto_reply_enabled: bool = False
    handoff_required: bool = True
    notes: str = ""


class KnowledgeItem(BaseModel):
    id: int | None = None
    title: str
    content: str
    source_type: str = "manual"
    tags: str = ""
    created_at: str = ""


class KnowledgeImportRequest(BaseModel):
    title: str = "商家话术导入"
    source_type: Literal["script", "faq", "product", "policy", "manual"] = "script"
    content: str = Field(min_length=1, max_length=20000)
    tags: str = ""
    sync_to_faq: bool = True


class KnowledgeImportResponse(BaseModel):
    imported: int
    faq_added: int
    items: list[KnowledgeItem]


class ReplyDraftRequest(BaseModel):
    channel: str = "wechat"
    message: str = Field(min_length=1, max_length=2000)
    customer_name: str = ""


class ReplyDraftResponse(BaseModel):
    channel: str
    mode: str
    reply: str
    need_followup: bool
    risk_flags: list[str]


class ServiceScriptGenerateRequest(BaseModel):
    channel: str = "wechat"
    scenario: Literal["new_customer", "price", "objection", "after_sale", "lead_capture", "full_pack"] = "full_pack"
    product_name: str = ""
    customer_pain: str = ""
    offer: str = ""
    tone: Literal["natural", "professional", "friendly", "urgent"] = "natural"
    save_to_knowledge: bool = True


class ServiceScriptStep(BaseModel):
    title: str
    message: str
    goal: str


class ServiceScriptGenerateResponse(BaseModel):
    title: str
    channel: str
    scenario: str
    opening: str
    steps: list[ServiceScriptStep]
    objection_replies: list[ServiceScriptStep]
    closing: str
    knowledge_imported: int = 0


def now_sql() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today_prefix() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def db_driver() -> str:
    return os.getenv("CS_DB_DRIVER", "sqlite").lower()


def mysql_config() -> dict[str, Any]:
    return {
        "host": os.getenv("CS_MYSQL_HOST", "127.0.0.1"),
        "port": int(os.getenv("CS_MYSQL_PORT", "3306")),
        "user": os.getenv("CS_MYSQL_USER", "root"),
        "password": os.getenv("CS_MYSQL_PASSWORD", ""),
        "database": os.getenv("CS_MYSQL_DATABASE", "ai_saas"),
        "charset": "utf8mb4",
        "cursorclass": None,
        "unix_socket": os.getenv("CS_MYSQL_UNIX_SOCKET") or None,
    }


@contextmanager
def db() -> Iterator[Any]:
    if db_driver() == "mysql":
        try:
            import pymysql
            import pymysql.cursors
        except ImportError as exc:
            raise RuntimeError("PyMySQL is not installed") from exc

        config = {key: value for key, value in mysql_config().items() if value not in {None, ""}}
        config["cursorclass"] = pymysql.cursors.DictCursor
        conn = pymysql.connect(**config)
        try:
            init_mysql(conn)
            yield MySQLAdapter(conn)
            conn.commit()
        finally:
            conn.close()
        return

    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        init_sqlite(conn)
        yield conn
        conn.commit()
    finally:
        conn.close()


class MySQLAdapter:
    def __init__(self, conn: Any):
        self.conn = conn

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        cursor = self.conn.cursor()
        cursor.execute(sql, params)
        return cursor


def param(sqlite: str = "?", mysql: str = "%s") -> str:
    return mysql if db_driver() == "mysql" else sqlite


def rows_to_dicts(rows: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def init_mysql(conn: Any) -> None:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS channel_configs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                merchant_id INT NOT NULL,
                channel VARCHAR(32) NOT NULL,
                display_name VARCHAR(80),
                mode VARCHAR(32) DEFAULT 'assist',
                status VARCHAR(32) DEFAULT 'draft',
                official_api_url TEXT,
                webhook_url TEXT,
                auto_reply_enabled TINYINT DEFAULT 0,
                handoff_required TINYINT DEFAULT 1,
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uniq_merchant_channel (merchant_id, channel)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """
        )
        cursor.execute(
            """
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'knowledge_base'
            """
        )
        knowledge_columns = {row["COLUMN_NAME"] if isinstance(row, dict) else row[0] for row in cursor.fetchall()}
        missing_knowledge_columns = {
            "merchant_id": "ALTER TABLE knowledge_base ADD COLUMN merchant_id INT NOT NULL DEFAULT 0",
            "title": "ALTER TABLE knowledge_base ADD COLUMN title VARCHAR(255)",
            "content": "ALTER TABLE knowledge_base ADD COLUMN content MEDIUMTEXT",
            "source_type": "ALTER TABLE knowledge_base ADD COLUMN source_type VARCHAR(32) DEFAULT 'manual'",
            "tags": "ALTER TABLE knowledge_base ADD COLUMN tags VARCHAR(255)",
            "created_at": "ALTER TABLE knowledge_base ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP",
            "updated_at": "ALTER TABLE knowledge_base ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP",
        }
        for column, ddl in missing_knowledge_columns.items():
            if column not in knowledge_columns:
                cursor.execute(ddl)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_base (
                id INT AUTO_INCREMENT PRIMARY KEY,
                merchant_id INT NOT NULL,
                title VARCHAR(255) NOT NULL,
                content MEDIUMTEXT NOT NULL,
                source_type VARCHAR(32) DEFAULT 'manual',
                tags VARCHAR(255),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """
        )


def init_sqlite(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS merchants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            business_name TEXT,
            phone TEXT,
            mobile TEXT,
            merchant_code TEXT UNIQUE,
            welcome_message TEXT,
            prompt_template TEXT,
            status INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            merchant_id INTEGER NOT NULL,
            name TEXT,
            phone TEXT,
            openid TEXT,
            intent_score INTEGER DEFAULT 0,
            is_high_intent INTEGER DEFAULT 0,
            followup_status TEXT DEFAULT 'pending',
            tags TEXT,
            last_query TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            merchant_id INTEGER NOT NULL,
            customer_id INTEGER,
            session_id TEXT,
            visitor_info TEXT,
            query TEXT NOT NULL,
            response TEXT,
            intent_score INTEGER DEFAULT 0,
            need_followup INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            merchant_id INTEGER,
            bot_id TEXT,
            user_id TEXT,
            query TEXT,
            response TEXT,
            created_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS channel_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            merchant_id INTEGER NOT NULL,
            channel TEXT NOT NULL,
            display_name TEXT,
            mode TEXT DEFAULT 'assist',
            status TEXT DEFAULT 'draft',
            official_api_url TEXT,
            webhook_url TEXT,
            auto_reply_enabled INTEGER DEFAULT 0,
            handoff_required INTEGER DEFAULT 1,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(merchant_id, channel)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_base (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            merchant_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            source_type TEXT DEFAULT 'manual',
            tags TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    count = conn.execute("SELECT COUNT(*) AS c FROM merchants").fetchone()["c"]
    if count == 0:
        conn.execute(
            """
            INSERT INTO merchants (username, password_hash, business_name, merchant_code, welcome_message, prompt_template, status)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            """,
            (
                "admin",
                hashlib.sha256("admin123".encode("utf-8")).hexdigest(),
                "演示商家",
                "WJDEMO001",
                "您好，我是演示商家的 AI 客服。请问想了解产品、价格还是合作？",
                json.dumps(default_profile_payload(), ensure_ascii=False),
            ),
        )


def default_profile_payload() -> dict[str, Any]:
    return {
        "industry": "通用服务",
        "business_intro": "我们提供面向商家的 AI 客服和增长自动化服务。",
        "products_services": "AI 客服、线索记录、自动回复、人工接管。",
        "pricing": "基础版 299 元/月起，定制部署单独报价。",
        "promotions": "新客户可先试用一个场景。",
        "hours": "工作日 9:00-21:00",
        "contact": "请留下手机号或微信，顾问会跟进。",
        "faq": [
            {"question": "能自动回复吗？", "answer": "可以在网页客服里自动回复；微信/抖音私信需要官方 API 权限。"},
            {"question": "可以试用吗？", "answer": "可以先配置一个测试商家和一个网页气泡试用。"},
        ],
    }


DEFAULT_CHANNELS: dict[str, tuple[str, str]] = {
    "web_widget": ("网页客服", "已支持自动回复和会话落库"),
    "wechat": ("微信客服", "建议接企业微信/微信客服官方 API；未授权前只生成回复草稿"),
    "douyin": ("抖音客服", "建议接抖音开放平台/企业号权限；未授权前只做人工辅助"),
    "taobao": ("淘宝客服", "建议接千牛/淘宝开放平台；未授权前只做话术建议"),
    "pdd": ("拼多多客服", "建议接拼多多开放平台；未授权前只做话术建议"),
}


def ensure_default_channels(merchant_id: int) -> None:
    marker = param()
    with db() as conn:
        for channel, (display_name, notes) in DEFAULT_CHANNELS.items():
            row = conn.execute(
                f"SELECT id FROM channel_configs WHERE merchant_id={marker} AND channel={marker}",
                (merchant_id, channel),
            ).fetchone()
            if row:
                continue
            conn.execute(
                f"""
                INSERT INTO channel_configs
                (merchant_id, channel, display_name, mode, status, official_api_url, webhook_url, auto_reply_enabled, handoff_required, notes, created_at, updated_at)
                VALUES ({marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker})
                """,
                (
                    merchant_id,
                    channel,
                    display_name,
                    "official_api" if channel == "web_widget" else "assist",
                    "connected" if channel == "web_widget" else "draft",
                    "",
                    "",
                    1 if channel == "web_widget" else 0,
                    0 if channel == "web_widget" else 1,
                    notes,
                    now_sql(),
                    now_sql(),
                ),
            )


def knowledge_rows(merchant_id: int, limit: int = 100) -> list[dict[str, Any]]:
    marker = param()
    with db() as conn:
        rows = conn.execute(
            f"""
            SELECT id,
                   COALESCE(title, '未命名知识') AS title,
                   COALESCE(content, '') AS content,
                   COALESCE(source_type, 'manual') AS source_type,
                   COALESCE(tags, '') AS tags,
                   COALESCE(created_at, '') AS created_at
            FROM knowledge_base
            WHERE merchant_id={marker}
            ORDER BY id DESC
            LIMIT {int(limit)}
            """,
            (merchant_id,),
        ).fetchall()
    return rows_to_dicts(rows)


def knowledge_context_for(merchant_id: int | None) -> str:
    if not merchant_id:
        return ""
    rows = knowledge_rows(merchant_id, limit=12)
    if not rows:
        return ""
    blocks = []
    for row in rows:
        blocks.append(f"- {row.get('title')}: {str(row.get('content') or '')[:700]}")
    return "\n".join(blocks)


def extract_knowledge_items(payload: KnowledgeImportRequest) -> list[KnowledgeItem]:
    lines = [line.strip(" \t-•") for line in payload.content.splitlines() if line.strip()]
    items: list[KnowledgeItem] = []
    pending_question = ""
    for line in lines:
        normalized = line.replace("：", ":")
        if normalized.lower().startswith(("q:", "问:", "问题:")):
            pending_question = normalized.split(":", 1)[1].strip()
            continue
        if normalized.lower().startswith(("a:", "答:", "答案:")) and pending_question:
            answer = normalized.split(":", 1)[1].strip()
            items.append(KnowledgeItem(title=pending_question[:120], content=answer, source_type=payload.source_type, tags=payload.tags))
            pending_question = ""
            continue
        if "=>" in line:
            title, content = line.split("=>", 1)
        elif "->" in line:
            title, content = line.split("->", 1)
        elif "：" in line:
            title, content = line.split("：", 1)
        elif ":" in line and len(line.split(":", 1)[0]) <= 40:
            title, content = line.split(":", 1)
        else:
            title, content = payload.title, line
        items.append(KnowledgeItem(title=title.strip()[:120] or payload.title, content=content.strip(), source_type=payload.source_type, tags=payload.tags))
    if not items:
        items.append(KnowledgeItem(title=payload.title, content=payload.content, source_type=payload.source_type, tags=payload.tags))
    return items[:80]


def parse_profile(row: dict[str, Any]) -> MerchantProfile:
    payload = default_profile_payload()
    raw = row.get("prompt_template") or ""
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                payload.update(parsed)
        except json.JSONDecodeError:
            payload["business_intro"] = raw

    return MerchantProfile(
        id=int(row["id"]),
        username=row.get("username") or "",
        merchant_code=row.get("merchant_code") or "",
        business_name=row.get("business_name") or "",
        welcome_message=row.get("welcome_message") or "您好，我是 AI 客服。请问有什么可以帮您？",
        prompt_template=row.get("prompt_template") or "",
        industry=payload.get("industry", "通用服务"),
        business_intro=payload.get("business_intro", ""),
        products_services=payload.get("products_services", ""),
        pricing=payload.get("pricing", ""),
        promotions=payload.get("promotions", ""),
        hours=payload.get("hours", ""),
        contact=payload.get("contact", ""),
        faq=[FAQItem.model_validate(item) for item in payload.get("faq", []) if isinstance(item, dict)],
    )


def profile_to_prompt(profile: MerchantProfile) -> str:
    payload = {
        "industry": profile.industry,
        "business_intro": profile.business_intro,
        "products_services": profile.products_services,
        "pricing": profile.pricing,
        "promotions": profile.promotions,
        "hours": profile.hours,
        "contact": profile.contact,
        "faq": [item.model_dump() for item in profile.faq],
    }
    return json.dumps(payload, ensure_ascii=False)


def verify_password(password: str, stored_hash: str) -> bool:
    if not stored_hash:
        return False
    if len(stored_hash) == 64 and all(ch in "0123456789abcdef" for ch in stored_hash.lower()):
        return hmac.compare_digest(hashlib.sha256(password.encode("utf-8")).hexdigest(), stored_hash)
    try:
        from werkzeug.security import check_password_hash

        return bool(check_password_hash(stored_hash, password))
    except Exception:
        return False


def auth_secret() -> str:
    return os.getenv("CS_AUTH_SECRET") or os.getenv("AI_API_KEY") or "dev-customer-service-secret"


def make_token(merchant_id: int) -> str:
    issued_at = str(int(time.time()))
    nonce = secrets.token_hex(8)
    payload = f"{merchant_id}.{issued_at}.{nonce}"
    signature = hmac.new(auth_secret().encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def parse_token(token: str) -> int:
    try:
        merchant_id, issued_at, nonce, signature = token.split(".", 3)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    payload = f"{merchant_id}.{issued_at}.{nonce}"
    expected = hmac.new(auth_secret().encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="Invalid token")
    return int(merchant_id)


def merchant_by_id(merchant_id: int) -> MerchantProfile:
    marker = param()
    with db() as conn:
        row = conn.execute(f"SELECT * FROM merchants WHERE id={marker} AND status=1", (merchant_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Merchant not found")
    return parse_profile(dict(row))


def merchant_by_code(merchant_code: str) -> MerchantProfile:
    marker = param()
    with db() as conn:
        row = conn.execute(f"SELECT * FROM merchants WHERE merchant_code={marker} AND status=1", (merchant_code,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Merchant code not found")
    return parse_profile(dict(row))


def current_merchant(authorization: str | None = Header(default=None)) -> MerchantProfile:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    return merchant_by_id(parse_token(authorization.split(" ", 1)[1].strip()))


def risk_flags_for(message: str) -> list[str]:
    terms = ["退款", "投诉", "付款", "转账", "账号", "密码", "隐私", "手机号", "地址", "发票", "合同"]
    return [term for term in terms if term in message]


def score_intent(message: str) -> int:
    score = 35
    for term in ["价格", "多少钱", "报价", "收费", "费用", "套餐", "试用", "购买", "合作", "电话", "微信", "预约", "演示", "接入", "官网", "网站"]:
        if term in message:
            score += 8
    return min(score, 95)


def local_grounded_reply(profile: MerchantProfile, message: str) -> str:
    wants_price = any(term in message for term in ["价格", "多少钱", "报价", "收费", "费用", "套餐"])
    wants_integration = any(term in message for term in ["接入", "官网", "网站", "网页", "代码", "气泡"])
    wants_function = any(term in message for term in ["功能", "能做", "自动回复", "客服", "会话", "线索"])

    parts: list[str] = []
    if wants_price and profile.pricing:
        parts.append(f"收费这块目前是：{profile.pricing}")
    if wants_integration:
        parts.append("可以接入官网。后台会生成一段 script 代码，放到客户网站后，右下角就会出现 AI 客服气泡。")
    if wants_function and profile.products_services:
        parts.append(f"现在能做的是：{profile.products_services}")
    if not parts:
        if profile.products_services:
            parts.append(f"我们主要提供：{profile.products_services}")
        else:
            parts.append("我先帮您记录需求，再给您推荐适合的接入方式。")
    if profile.promotions and wants_price:
        parts.append(f"优惠：{profile.promotions}")
    parts.append("您方便发一下网站地址或行业类型吗？我可以判断适合直接接入，还是需要先整理 FAQ。")
    return "\n".join(parts)


def is_generic_ai_reply(reply: str) -> bool:
    text = reply.strip()
    if len(text) < 35:
        return True
    generic_markers = ["有什么我可以帮", "欢迎随时提问", "请问有什么", "我可以帮您", "具体想了解", "我会尽力帮助"]
    return any(marker in text for marker in generic_markers) and not any(
        marker in text for marker in ["价格", "收费", "套餐", "接入", "气泡", "线索", "人工接管", "官方 API", "开放平台"]
    )


def channel_grounded_reply(profile: MerchantProfile, message: str, channel: str) -> str:
    channel_name = DEFAULT_CHANNELS.get(channel, DEFAULT_CHANNELS["web_widget"])[0]
    if channel == "web_widget":
        return local_grounded_reply(profile, message)
    parts = [
        f"可以做{channel_name}客服接入，但建议按两步走：",
        f"1. 现在先把商家的话术、商品、价格、售后政策导入知识库，系统生成{channel_name}拟人工回复草稿，由人工确认后发送。",
        f"2. 拿到{channel_name}官方 API/开放平台权限后，再把回复草稿接入自动回复流程。",
        "不建议用脚本模拟点击私信或冒充真人自动发送，这类方式容易触发平台风控。"
    ]
    if profile.products_services:
        parts.append(f"当前系统已具备：{profile.products_services}")
    parts.append(f"您可以先发一份{channel_name}常见问题话术，我帮您导入知识库并生成测试回复。")
    return "\n".join(parts)


def scenario_name(scenario: str) -> str:
    names = {
        "new_customer": "新客开场",
        "price": "价格咨询",
        "objection": "异议处理",
        "after_sale": "售后安抚",
        "lead_capture": "留资转化",
        "full_pack": "完整成交脚本",
    }
    return names.get(scenario, "客服脚本")


def tone_instruction(tone: str) -> str:
    return {
        "natural": "像熟练真人客服，短句、自然、有来有回",
        "professional": "专业克制，重点清楚，适合企业服务",
        "friendly": "亲和热情，适合本地生活和电商",
        "urgent": "更强调限时优惠和下一步行动，但不要夸大承诺",
    }.get(tone, "自然")


def script_as_text(script: ServiceScriptGenerateResponse) -> str:
    lines = [f"# {script.title}", "", f"渠道：{DEFAULT_CHANNELS.get(script.channel, DEFAULT_CHANNELS['web_widget'])[0]}", f"场景：{scenario_name(script.scenario)}", "", "## 开场", script.opening, "", "## 跟进步骤"]
    for index, step in enumerate(script.steps, 1):
        lines.extend([f"{index}. {step.title}", f"话术：{step.message}", f"目标：{step.goal}", ""])
    lines.append("## 异议处理")
    for step in script.objection_replies:
        lines.extend([f"- {step.title}", f"  话术：{step.message}", f"  目标：{step.goal}"])
    lines.extend(["", "## 收口", script.closing])
    return "\n".join(lines)


def fallback_service_script(profile: MerchantProfile, payload: ServiceScriptGenerateRequest) -> ServiceScriptGenerateResponse:
    channel_name = DEFAULT_CHANNELS.get(payload.channel, DEFAULT_CHANNELS["web_widget"])[0]
    product = payload.product_name or profile.products_services or profile.business_name or "我们的服务"
    pain = payload.customer_pain or "客户想更快解决咨询和转化问题"
    offer = payload.offer or profile.promotions or profile.pricing or "可以先安排一次试用/演示"
    style = tone_instruction(payload.tone)
    title = f"{channel_name}｜{scenario_name(payload.scenario)}｜{product}"
    opening = f"您好，我是{profile.business_name or '商家'}的客服。看到您在了解{product}，我先简单确认一下：您现在主要是想解决「{pain}」这个问题吗？"
    steps = [
        ServiceScriptStep(
            title="确认需求",
            message=f"我先确认下您的情况：您现在更关注价格、效果、接入方式，还是售后保障？这样我能直接给您对应方案。",
            goal="让客户说出真实需求，避免一上来硬推。",
        ),
        ServiceScriptStep(
            title="给出方案",
            message=f"按您这个需求，{product}比较适合先从基础场景接入：先把常见问题自动回复跑起来，再把高意向客户交给人工跟进。",
            goal="把产品能力和客户问题对上。",
        ),
        ServiceScriptStep(
            title="报价和优惠",
            message=f"费用这块可以按套餐走，当前参考是：{profile.pricing or offer}。如果您现在确定要试，我们可以先给您配置一个测试场景。",
            goal="回答价格，同时给出低门槛下一步。",
        ),
        ServiceScriptStep(
            title="推进留资",
            message="您方便留一个手机号或微信吗？我把测试入口和接入方式发您，后面也方便帮您看配置结果。",
            goal="拿到可跟进线索。",
        ),
    ]
    objection_replies = [
        ServiceScriptStep(
            title="客户说太贵",
            message="理解，前期不用一次上完整版本。可以先跑一个核心场景，看每天能省多少客服时间、能沉淀多少线索，再决定是否升级。",
            goal="降低决策压力。",
        ),
        ServiceScriptStep(
            title="客户担心效果",
            message="可以先用您现有话术做测试，不满意就继续调知识库和回复风格。我们不建议一开始承诺效果，先看真实会话数据。",
            goal="建立可信预期。",
        ),
        ServiceScriptStep(
            title="客户问平台私信",
            message=f"{channel_name}如果要自动发消息，需要官方 API/开放平台权限。没有权限前我们只做回复草稿和人工确认，不做脚本模拟发送。",
            goal="说明合规边界。",
        ),
    ]
    closing = f"总结一下：先导入话术和 FAQ，再开一个测试场景，跑通后再扩展到{channel_name}。{offer}。您把现有客服话术发我，我可以先帮您整理第一版。"
    return ServiceScriptGenerateResponse(
        title=title,
        channel=payload.channel,
        scenario=payload.scenario,
        opening=opening,
        steps=steps,
        objection_replies=objection_replies,
        closing=closing,
    )


def call_ai_service_script(profile: MerchantProfile, payload: ServiceScriptGenerateRequest) -> ServiceScriptGenerateResponse:
    prompt = f"""
请为商家生成一套可直接给客服使用的成交客服脚本，必须输出 JSON。

商家：{profile.business_name}
行业：{profile.industry}
业务介绍：{profile.business_intro}
商品/服务：{profile.products_services}
价格：{profile.pricing}
优惠：{profile.promotions}
渠道：{DEFAULT_CHANNELS.get(payload.channel, DEFAULT_CHANNELS['web_widget'])[0]}
场景：{scenario_name(payload.scenario)}
产品名：{payload.product_name}
客户痛点：{payload.customer_pain}
优惠/承诺边界：{payload.offer}
语气：{tone_instruction(payload.tone)}

JSON 结构：
{{
  "title": "...",
  "opening": "...",
  "steps": [{{"title": "...", "message": "...", "goal": "..."}}],
  "objection_replies": [{{"title": "...", "message": "...", "goal": "..."}}],
  "closing": "..."
}}

要求：
1. 不要夸大承诺，不承诺退款和收益。
2. 微信、抖音、淘宝、拼多多如果涉及自动发送，必须提示需要官方 API 权限。
3. 每条话术像真人客服，短、自然、能推进下一步。
"""
    try:
        raw = call_ai_reply(profile, prompt, [])
        start = raw.find("{")
        end = raw.rfind("}")
        parsed = json.loads(raw[start : end + 1] if start >= 0 and end > start else raw)
        return ServiceScriptGenerateResponse(
            title=str(parsed.get("title") or f"{DEFAULT_CHANNELS.get(payload.channel, DEFAULT_CHANNELS['web_widget'])[0]}客服脚本"),
            channel=payload.channel,
            scenario=payload.scenario,
            opening=str(parsed.get("opening") or ""),
            steps=[ServiceScriptStep.model_validate(item) for item in parsed.get("steps", [])[:8] if isinstance(item, dict)],
            objection_replies=[ServiceScriptStep.model_validate(item) for item in parsed.get("objection_replies", [])[:8] if isinstance(item, dict)],
            closing=str(parsed.get("closing") or ""),
        )
    except Exception:
        return fallback_service_script(profile, payload)


def build_system_prompt(profile: MerchantProfile) -> str:
    faq = "\n".join(f"- Q: {item.question}\n  A: {item.answer}" for item in profile.faq)
    knowledge = knowledge_context_for(profile.id)
    return f"""
你是 {profile.business_name or profile.username} 的网站 AI 客服。你只能根据商家资料回答，不能编造价格、承诺效果、承诺退款。

行业：{profile.industry}
业务介绍：{profile.business_intro}
商品/服务：{profile.products_services}
价格/套餐：{profile.pricing}
优惠活动：{profile.promotions}
营业时间：{profile.hours}
联系方式：{profile.contact}
FAQ：
{faq}
导入知识库/话术：
{knowledge or "暂无额外导入知识。"}

回复要求：
1. 用中文，像真人客服，简短自然。
2. 先回答客户当前问题，再推进下一步。
3. 如果信息不足，问 1 个关键问题。
4. 对高风险问题保持谨慎，不承诺不确定事项。
5. 需要留资时，温和引导客户留下电话或微信。
"""


def call_ai_reply(profile: MerchantProfile, message: str, history: list[dict[str, Any]]) -> str:
    api_key = os.getenv("AI_API_KEY") or os.getenv("OPENAI_API_KEY")
    model = os.getenv("AI_MODEL")
    base_url = os.getenv("AI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    if not api_key or not model:
        raise RuntimeError("AI provider is not configured")

    history_messages = []
    for item in history[-6:]:
        if item.get("query"):
            history_messages.append({"role": "user", "content": str(item["query"])[:800]})
        if item.get("response"):
            history_messages.append({"role": "assistant", "content": str(item["response"])[:800]})

    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": build_system_prompt(profile)},
            *history_messages,
            {"role": "user", "content": message},
        ],
        "temperature": float(os.getenv("AI_TEMPERATURE", "0.7")),
    }
    endpoint = f"{base_url}/chat/completions" if base_url.endswith("/v1") else f"{base_url}/v1/chat/completions"
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=float(os.getenv("AI_TIMEOUT", "45"))) as response:
        data = json.loads(response.read().decode("utf-8"))
    return str(data["choices"][0]["message"]["content"]).strip()


def fallback_reply(profile: MerchantProfile, message: str) -> str:
    if risk_flags_for(message):
        return "这个问题我先帮您记录下来，涉及订单、付款、退款或账号信息时需要人工客服确认。您可以留下联系方式，我们尽快跟进。"
    return local_grounded_reply(profile, message)


def conversation_history(session_id: str) -> list[dict[str, Any]]:
    marker = param()
    with db() as conn:
        rows = conn.execute(
            f"SELECT query, response, created_at FROM conversations WHERE session_id={marker} ORDER BY id ASC",
            (session_id,),
        ).fetchall()
    return rows_to_dicts(rows)


def upsert_customer(merchant_id: int, visitor_id: str, message: str, intent_score: int, need_followup: bool) -> int:
    marker = param()
    with db() as conn:
        row = conn.execute(
            f"SELECT id FROM customers WHERE merchant_id={marker} AND openid={marker}",
            (merchant_id, visitor_id),
        ).fetchone()
        if row:
            conn.execute(
                f"""
                UPDATE customers
                SET last_query={marker}, intent_score={marker}, is_high_intent={marker}, updated_at={marker}
                WHERE id={marker}
                """,
                (message, intent_score, 1 if intent_score >= 70 else 0, now_sql(), dict(row)["id"]),
            )
            return int(dict(row)["id"])
        cursor = conn.execute(
            f"""
            INSERT INTO customers (merchant_id, name, openid, intent_score, is_high_intent, followup_status, last_query, created_at, updated_at)
            VALUES ({marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker})
            """,
            (
                merchant_id,
                f"访客{visitor_id[-6:]}",
                visitor_id,
                intent_score,
                1 if need_followup or intent_score >= 70 else 0,
                "needs_followup" if need_followup else "pending",
                message,
                now_sql(),
                now_sql(),
            ),
        )
        return int(cursor.lastrowid)


@router.post("/auth/login", response_model=AuthLoginResponse)
async def auth_login(payload: AuthLoginRequest) -> AuthLoginResponse:
    marker = param()
    with db() as conn:
        row = conn.execute(f"SELECT * FROM merchants WHERE username={marker} AND status=1", (payload.username,)).fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    data = dict(row)
    if not verify_password(payload.password, data.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    profile = parse_profile(data)
    return AuthLoginResponse(token=make_token(profile.id or 0), merchant=profile)


@router.get("/merchant/profile", response_model=MerchantProfile)
async def get_merchant_profile(merchant: MerchantProfile = Depends(current_merchant)) -> MerchantProfile:
    return merchant


@router.get("/channels", response_model=list[ChannelConfig])
async def list_channels(merchant: MerchantProfile = Depends(current_merchant)) -> list[ChannelConfig]:
    ensure_default_channels(merchant.id or 0)
    marker = param()
    with db() as conn:
        rows = conn.execute(
            f"""
            SELECT channel, display_name, mode, status, official_api_url, webhook_url,
                   auto_reply_enabled, handoff_required, notes
            FROM channel_configs
            WHERE merchant_id={marker}
            ORDER BY FIELD(channel, 'web_widget', 'wechat', 'douyin', 'taobao', 'pdd'), channel
            """ if db_driver() == "mysql" else f"""
            SELECT channel, display_name, mode, status, official_api_url, webhook_url,
                   auto_reply_enabled, handoff_required, notes
            FROM channel_configs
            WHERE merchant_id={marker}
            ORDER BY CASE channel
                WHEN 'web_widget' THEN 1
                WHEN 'wechat' THEN 2
                WHEN 'douyin' THEN 3
                WHEN 'taobao' THEN 4
                WHEN 'pdd' THEN 5
                ELSE 9
            END, channel
            """,
            (merchant.id,),
        ).fetchall()
    return [
        ChannelConfig(
            channel=row["channel"],
            display_name=row.get("display_name") or row["channel"],
            mode=row.get("mode") or "assist",
            status=row.get("status") or "draft",
            official_api_url=row.get("official_api_url") or "",
            webhook_url=row.get("webhook_url") or "",
            auto_reply_enabled=bool(row.get("auto_reply_enabled")),
            handoff_required=bool(row.get("handoff_required")),
            notes=row.get("notes") or "",
        )
        for row in rows_to_dicts(rows)
    ]


@router.put("/channels/{channel}", response_model=ChannelConfig)
async def update_channel(channel: str, payload: ChannelConfigUpdate, merchant: MerchantProfile = Depends(current_merchant)) -> ChannelConfig:
    ensure_default_channels(merchant.id or 0)
    if channel not in DEFAULT_CHANNELS:
        raise HTTPException(status_code=404, detail="Channel not supported")
    marker = param()
    display_name = payload.display_name or DEFAULT_CHANNELS[channel][0]
    with db() as conn:
        conn.execute(
            f"""
            UPDATE channel_configs
            SET display_name={marker}, mode={marker}, status={marker}, official_api_url={marker},
                webhook_url={marker}, auto_reply_enabled={marker}, handoff_required={marker}, notes={marker}, updated_at={marker}
            WHERE merchant_id={marker} AND channel={marker}
            """,
            (
                display_name,
                payload.mode,
                payload.status,
                payload.official_api_url,
                payload.webhook_url,
                1 if payload.auto_reply_enabled else 0,
                1 if payload.handoff_required else 0,
                payload.notes,
                now_sql(),
                merchant.id,
                channel,
            ),
        )
    return [item for item in await list_channels(merchant) if item.channel == channel][0]


@router.get("/knowledge", response_model=list[KnowledgeItem])
async def list_knowledge(merchant: MerchantProfile = Depends(current_merchant)) -> list[KnowledgeItem]:
    return [KnowledgeItem(**row) for row in knowledge_rows(merchant.id or 0)]


@router.post("/knowledge/import", response_model=KnowledgeImportResponse)
async def import_knowledge(payload: KnowledgeImportRequest, merchant: MerchantProfile = Depends(current_merchant)) -> KnowledgeImportResponse:
    items = extract_knowledge_items(payload)
    marker = param()
    created: list[KnowledgeItem] = []
    with db() as conn:
        for item in items:
            cursor = conn.execute(
                f"""
                INSERT INTO knowledge_base (merchant_id, title, content, source_type, tags, created_at, updated_at)
                VALUES ({marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker})
                """,
                (merchant.id, item.title, item.content, item.source_type, item.tags, now_sql(), now_sql()),
            )
            created.append(item.model_copy(update={"id": getattr(cursor, "lastrowid", None), "created_at": now_sql()}))

    faq_added = 0
    if payload.sync_to_faq:
        profile = merchant_by_id(merchant.id or 0)
        existing = {faq.question.strip() for faq in profile.faq}
        next_faq = list(profile.faq)
        for item in items:
            if item.title and item.content and item.title not in existing:
                next_faq.append(FAQItem(question=item.title, answer=item.content))
                existing.add(item.title)
                faq_added += 1
        profile.faq = next_faq[:80]
        marker = param()
        with db() as conn:
            conn.execute(
                f"UPDATE merchants SET prompt_template={marker}, updated_at={marker} WHERE id={marker}",
                (profile_to_prompt(profile), now_sql(), merchant.id),
            )

    return KnowledgeImportResponse(imported=len(created), faq_added=faq_added, items=created)


@router.post("/reply/draft", response_model=ReplyDraftResponse)
async def reply_draft(payload: ReplyDraftRequest, merchant: MerchantProfile = Depends(current_merchant)) -> ReplyDraftResponse:
    channel = payload.channel if payload.channel in DEFAULT_CHANNELS else "web_widget"
    flags = risk_flags_for(payload.message)
    need_followup = bool(flags)
    try:
        reply = call_ai_reply(merchant, f"渠道：{DEFAULT_CHANNELS[channel][0]}\n客户：{payload.customer_name}\n消息：{payload.message}", [])
        if is_generic_ai_reply(reply):
            reply = channel_grounded_reply(merchant, payload.message, channel)
    except Exception:
        reply = channel_grounded_reply(merchant, payload.message, channel)
        need_followup = True
    if channel != "web_widget":
        reply = f"{reply}\n\n内部提示：当前为{DEFAULT_CHANNELS[channel][0]}回复草稿，请人工确认后再发送；接官方 API 后可切换自动回复。"
    return ReplyDraftResponse(channel=channel, mode="assist" if channel != "web_widget" else "official_api", reply=reply, need_followup=need_followup, risk_flags=flags)


@router.post("/service-scripts/generate", response_model=ServiceScriptGenerateResponse)
async def generate_service_script(payload: ServiceScriptGenerateRequest, merchant: MerchantProfile = Depends(current_merchant)) -> ServiceScriptGenerateResponse:
    if payload.channel not in DEFAULT_CHANNELS:
        raise HTTPException(status_code=404, detail="Channel not supported")
    script = call_ai_service_script(merchant, payload)
    imported = 0
    if payload.save_to_knowledge:
        marker = param()
        with db() as conn:
            conn.execute(
                f"""
                INSERT INTO knowledge_base (merchant_id, title, content, source_type, tags, created_at, updated_at)
                VALUES ({marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker})
                """,
                (
                    merchant.id,
                    script.title,
                    script_as_text(script),
                    "script",
                    f"{payload.channel},{payload.scenario},客服脚本",
                    now_sql(),
                    now_sql(),
                ),
            )
            imported = 1
    return script.model_copy(update={"knowledge_imported": imported})


@router.put("/merchant/profile", response_model=MerchantProfile)
async def update_merchant_profile(payload: MerchantProfile, merchant: MerchantProfile = Depends(current_merchant)) -> MerchantProfile:
    profile = payload.model_copy(update={"id": merchant.id, "username": merchant.username, "merchant_code": merchant.merchant_code})
    marker = param()
    with db() as conn:
        conn.execute(
            f"""
            UPDATE merchants
            SET business_name={marker}, welcome_message={marker}, prompt_template={marker}, updated_at={marker}
            WHERE id={marker}
            """,
            (profile.business_name, profile.welcome_message, profile_to_prompt(profile), now_sql(), merchant.id),
        )
    return merchant_by_id(merchant.id or 0)


@router.get("/dashboard/overview", response_model=DashboardOverview)
async def dashboard_overview(merchant: MerchantProfile = Depends(current_merchant)) -> DashboardOverview:
    ensure_default_channels(merchant.id or 0)
    marker = param()
    today = f"{today_prefix()}%"
    with db() as conn:
        today_conversations = dict(conn.execute(
            f"SELECT COUNT(*) AS c FROM conversations WHERE merchant_id={marker} AND created_at LIKE {marker}",
            (merchant.id, today),
        ).fetchone())["c"]
        auto_replies = dict(conn.execute(
            f"SELECT COUNT(*) AS c FROM chat_logs WHERE merchant_id={marker} AND created_at LIKE {marker}",
            (merchant.id, today),
        ).fetchone())["c"]
        leads = dict(conn.execute(f"SELECT COUNT(*) AS c FROM customers WHERE merchant_id={marker}", (merchant.id,)).fetchone())["c"]
        handoff = dict(conn.execute(
            f"SELECT COUNT(*) AS c FROM conversations WHERE merchant_id={marker} AND need_followup=1",
            (merchant.id,),
        ).fetchone())["c"]
        knowledge_count = dict(conn.execute(
            f"SELECT COUNT(*) AS c FROM knowledge_base WHERE merchant_id={marker}",
            (merchant.id,),
        ).fetchone())["c"]
        enabled_channels = dict(conn.execute(
            f"SELECT COUNT(*) AS c FROM channel_configs WHERE merchant_id={marker} AND status IN ({marker}, {marker})",
            (merchant.id, "ready", "connected"),
        ).fetchone())["c"]
    ai_mode = "ai" if os.getenv("AI_API_KEY") and os.getenv("AI_MODEL") else "template"
    return DashboardOverview(
        today_conversations=int(today_conversations),
        auto_replies=int(auto_replies),
        leads=int(leads),
        handoff_needed=int(handoff),
        ai_mode=ai_mode,
        knowledge_items=int(knowledge_count),
        enabled_channels=int(enabled_channels),
    )


@router.post("/widget/session", response_model=WidgetSessionResponse)
async def widget_session(payload: WidgetSessionRequest) -> WidgetSessionResponse:
    profile = merchant_by_code(payload.merchant_code)
    visitor_id = payload.visitor_id or secrets.token_hex(8)
    return WidgetSessionResponse(
        session_id=str(uuid.uuid4()),
        visitor_id=visitor_id,
        merchant_code=payload.merchant_code,
        welcome_message=profile.welcome_message,
        business_name=profile.business_name or profile.username,
    )


@router.post("/widget/message", response_model=WidgetMessageResponse)
async def widget_message(payload: WidgetMessageRequest, request: Request) -> WidgetMessageResponse:
    profile = merchant_by_code(payload.merchant_code)
    visitor_id = payload.visitor_id or secrets.token_hex(8)
    flags = risk_flags_for(payload.message)
    intent_score = score_intent(payload.message)
    need_followup = bool(flags) or intent_score >= 70
    history = conversation_history(payload.session_id)
    try:
        reply = call_ai_reply(profile, payload.message, history)
        if is_generic_ai_reply(reply):
            reply = local_grounded_reply(profile, payload.message)
    except Exception:
        reply = fallback_reply(profile, payload.message)
        need_followup = True

    customer_id = upsert_customer(profile.id or 0, visitor_id, payload.message, intent_score, need_followup)
    visitor_info = json.dumps(
        {"visitor_id": visitor_id, "page_url": payload.page_url, "ip": request.client.host if request.client else ""},
        ensure_ascii=False,
    )
    marker = param()
    with db() as conn:
        conn.execute(
            f"""
            INSERT INTO conversations (merchant_id, customer_id, session_id, visitor_info, query, response, intent_score, need_followup, created_at)
            VALUES ({marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker})
            """,
            (profile.id, customer_id, payload.session_id, visitor_info, payload.message, reply, intent_score, 1 if need_followup else 0, now_sql()),
        )
        conn.execute(
            f"""
            INSERT INTO chat_logs (merchant_id, bot_id, user_id, query, response, created_at)
            VALUES ({marker}, {marker}, {marker}, {marker}, {marker}, {marker})
            """,
            (profile.id, profile.merchant_code, visitor_id, payload.message, reply, now_sql()),
        )
    return WidgetMessageResponse(
        session_id=payload.session_id,
        customer_message=payload.message,
        ai_reply=reply,
        intent_score=intent_score,
        need_followup=need_followup,
        risk_flags=flags,
    )


@router.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations(merchant: MerchantProfile = Depends(current_merchant)) -> list[ConversationSummary]:
    marker = param()
    with db() as conn:
        rows = conn.execute(
            f"""
            SELECT session_id,
                   MAX(customer_id) AS customer_id,
                   MAX(query) AS last_query,
                   MAX(response) AS last_response,
                   MAX(intent_score) AS intent_score,
                   MAX(need_followup) AS need_followup,
                   COUNT(*) AS message_count,
                   MAX(created_at) AS updated_at
            FROM conversations
            WHERE merchant_id={marker}
            GROUP BY session_id
            ORDER BY updated_at DESC
            LIMIT 100
            """,
            (merchant.id,),
        ).fetchall()
    return [
        ConversationSummary(
            session_id=str(row["session_id"]),
            customer_id=row["customer_id"],
            visitor_name=f"访客{str(row['session_id'])[-6:]}",
            last_query=row["last_query"] or "",
            last_response=row["last_response"] or "",
            intent_score=int(row["intent_score"] or 0),
            need_followup=bool(row["need_followup"]),
            message_count=int(row["message_count"] or 0),
            updated_at=str(row["updated_at"] or ""),
        )
        for row in rows_to_dicts(rows)
    ]


@router.get("/conversations/{session_id}", response_model=ConversationDetail)
async def conversation_detail(session_id: str, merchant: MerchantProfile = Depends(current_merchant)) -> ConversationDetail:
    marker = param()
    with db() as conn:
        rows = conn.execute(
            f"SELECT query, response, intent_score, need_followup, created_at FROM conversations WHERE merchant_id={marker} AND session_id={marker} ORDER BY id ASC",
            (merchant.id, session_id),
        ).fetchall()
    messages: list[dict[str, Any]] = []
    for row in rows_to_dicts(rows):
        messages.append({"role": "visitor", "text": row.get("query", ""), "created_at": row.get("created_at")})
        messages.append({"role": "assistant", "text": row.get("response", ""), "created_at": row.get("created_at"), "intent_score": row.get("intent_score"), "need_followup": bool(row.get("need_followup"))})
    return ConversationDetail(session_id=session_id, messages=messages)


@router.post("/conversations/{session_id}/handoff", response_model=HandoffResponse)
async def mark_handoff(session_id: str, merchant: MerchantProfile = Depends(current_merchant)) -> HandoffResponse:
    marker = param()
    with db() as conn:
        conn.execute(
            f"UPDATE conversations SET need_followup=1 WHERE merchant_id={marker} AND session_id={marker}",
            (merchant.id, session_id),
        )
    return HandoffResponse(session_id=session_id, need_followup=True)


@router.get("/widget.js")
async def widget_js(merchant_code: str = Query(...)) -> Response:
    js = f"""
(function() {{
  var merchantCode = {json.dumps(merchant_code)};
  var scriptUrl = new URL(document.currentScript.src);
  var apiBase = scriptUrl.origin + scriptUrl.pathname.replace(/\\/widget\\.js$/, "");
  var sessionId = localStorage.getItem("wj_ai_cs_session_" + merchantCode);
  var visitorId = localStorage.getItem("wj_ai_cs_visitor_" + merchantCode) || Math.random().toString(16).slice(2);
  localStorage.setItem("wj_ai_cs_visitor_" + merchantCode, visitorId);
  var root = document.createElement("div");
  root.id = "wj-ai-cs";
  root.innerHTML = '<button class="wj-cs-toggle">AI客服</button><div class="wj-cs-panel"><div class="wj-cs-head">在线客服<span>×</span></div><div class="wj-cs-msgs"></div><form class="wj-cs-form"><input placeholder="输入您的问题" /><button>发送</button></form></div>';
  document.body.appendChild(root);
  var style = document.createElement("style");
  style.textContent = '#wj-ai-cs{{position:fixed;right:22px;bottom:22px;z-index:2147483647;font-family:system-ui,Microsoft YaHei,sans-serif}}#wj-ai-cs .wj-cs-toggle{{border:0;border-radius:999px;padding:13px 18px;background:#111827;color:#fff;box-shadow:0 12px 30px rgba(0,0,0,.24);cursor:pointer}}#wj-ai-cs .wj-cs-panel{{display:none;width:340px;height:460px;background:#fff;border:1px solid #e5e7eb;border-radius:14px;box-shadow:0 20px 60px rgba(0,0,0,.22);overflow:hidden}}#wj-ai-cs.open .wj-cs-panel{{display:flex;flex-direction:column}}#wj-ai-cs.open .wj-cs-toggle{{display:none}}.wj-cs-head{{display:flex;justify-content:space-between;align-items:center;padding:14px 16px;background:#111827;color:#fff;font-weight:700}}.wj-cs-head span{{cursor:pointer;font-size:20px}}.wj-cs-msgs{{flex:1;overflow:auto;padding:14px;background:#f8fafc}}.wj-cs-msg{{margin:8px 0;padding:10px 12px;border-radius:12px;line-height:1.45;font-size:14px;white-space:pre-wrap}}.wj-cs-msg.bot{{background:#fff;border:1px solid #e5e7eb;color:#111827}}.wj-cs-msg.me{{background:#2563eb;color:#fff;margin-left:42px}}.wj-cs-form{{display:flex;gap:8px;padding:12px;border-top:1px solid #e5e7eb}}.wj-cs-form input{{flex:1;border:1px solid #d1d5db;border-radius:9px;padding:10px}}.wj-cs-form button{{border:0;border-radius:9px;background:#111827;color:#fff;padding:0 14px}}';
  document.head.appendChild(style);
  var panel = root.querySelector(".wj-cs-panel");
  var msgs = root.querySelector(".wj-cs-msgs");
  var form = root.querySelector(".wj-cs-form");
  var input = form.querySelector("input");
  function add(role, text) {{
    var item = document.createElement("div");
    item.className = "wj-cs-msg " + (role === "me" ? "me" : "bot");
    item.textContent = text;
    msgs.appendChild(item);
    msgs.scrollTop = msgs.scrollHeight;
  }}
  function ensureSession() {{
    if (sessionId) return Promise.resolve();
    return fetch(apiBase + "/widget/session", {{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{merchant_code:merchantCode,visitor_id:visitorId,page_url:location.href,user_agent:navigator.userAgent}})}})
      .then(function(r){{return r.json()}})
      .then(function(data){{sessionId=data.session_id;localStorage.setItem("wj_ai_cs_session_" + merchantCode, sessionId);add("bot", data.welcome_message || "您好，请问有什么可以帮您？");}});
  }}
  root.querySelector(".wj-cs-toggle").onclick = function() {{ root.classList.add("open"); ensureSession(); }};
  root.querySelector(".wj-cs-head span").onclick = function() {{ root.classList.remove("open"); }};
  form.onsubmit = function(e) {{
    e.preventDefault();
    var text = input.value.trim();
    if (!text) return;
    input.value = "";
    add("me", text);
    ensureSession().then(function(){{
      add("bot", "正在回复...");
      return fetch(apiBase + "/widget/message", {{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{merchant_code:merchantCode,session_id:sessionId,visitor_id:visitorId,message:text,page_url:location.href}})}});
    }}).then(function(r){{return r.json()}}).then(function(data){{msgs.lastChild.textContent=data.ai_reply || "已收到，我稍后回复您。";}}).catch(function(){{msgs.lastChild.textContent="网络异常，请稍后再试。";}});
  }};
}})();
"""
    return Response(js, media_type="application/javascript; charset=utf-8")


@router.get("/widget-test", response_class=HTMLResponse)
async def widget_test(merchant_code: str = Query("WJDEMO001")) -> str:
    return f"""<!doctype html><html><head><meta charset='utf-8'><title>AI 客服测试</title></head><body style='font-family:system-ui,Microsoft YaHei,sans-serif;padding:40px'><h1>AI 客服气泡测试页</h1><p>右下角应该出现客服气泡。</p><script src="./widget.js?merchant_code={merchant_code}"></script></body></html>"""
