from __future__ import annotations

import hashlib
import json
import re
import socket
import uuid
from typing import Any, Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field

from backend.customer_service_saas import (
    DATA_DIR,
    MerchantProfile,
    db,
    db_driver,
    ensure_followup_task,
    join_tags,
    knowledge_context_for,
    knowledge_rows,
    now_sql,
    param,
    record_audit_log,
    record_usage,
    rows_to_dicts,
    upsert_customer,
)
from backend.platform.ai_engine import default_ai_engine
from backend.platform.workflow import workflow_engine


DesktopAgentMode = Literal["assist", "auto_paste", "auto_send", "paused"]
DesktopAgentAction = Literal["none", "draft_only", "paste_reply", "send_reply", "handoff"]
DesktopAgentSource = Literal["uia", "ocr", "clipboard", "mock", "unknown"]

CONFIRM_DESKTOP_AUTO_SEND = "CONFIRM_DESKTOP_AUTO_SEND"


class DesktopAgentSessionRequest(BaseModel):
    session_id: str = ""
    device_name: str = ""
    os_name: str = ""
    platform: str = "auto"
    app_version: str = ""
    mode: DesktopAgentMode = "assist"
    paused: bool = False
    auto_send_confirmed: bool = False
    window_allowlist: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DesktopAgentSessionItem(BaseModel):
    session_id: str
    merchant_id: int
    device_name: str = ""
    os_name: str = ""
    platform: str = "auto"
    app_version: str = ""
    mode: DesktopAgentMode = "assist"
    paused: bool = False
    auto_send_confirmed: bool = False
    window_allowlist: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    last_heartbeat_at: str = ""
    created_at: str = ""
    updated_at: str = ""


class DesktopAgentSessionResponse(BaseModel):
    session: DesktopAgentSessionItem
    paused: bool
    effective_mode: DesktopAgentMode
    confirm_auto_send_phrase: str = CONFIRM_DESKTOP_AUTO_SEND
    next_action: str = ""


class DesktopAgentEventRequest(BaseModel):
    session_id: str = Field(min_length=1)
    platform: str = "auto"
    channel: str = ""
    window_title: str = ""
    window_id: str = ""
    source: DesktopAgentSource = "unknown"
    message_text: str = Field(min_length=1, max_length=12000)
    message_hash: str = ""
    mode: DesktopAgentMode | None = None
    auto_send_enabled: bool = False
    auto_send_confirm_phrase: str = ""
    local_paused: bool = False
    reply_goal: str = ""
    merchant_profile: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class DesktopAgentDecision(BaseModel):
    event_id: int | None = None
    action_id: str = ""
    session_id: str
    action: DesktopAgentAction
    should_reply: bool = False
    reply_text: str = ""
    risk_flags: list[str] = Field(default_factory=list)
    intent_score: int = 0
    mode: DesktopAgentMode = "assist"
    paused: bool = False
    idempotent: bool = False
    message_hash: str = ""
    workflow_run_ids: list[str] = Field(default_factory=list)
    reason: str = ""
    safety_checks: dict[str, Any] = Field(default_factory=dict)
    reply_meta: dict[str, Any] = Field(default_factory=dict)


class DesktopAgentActionResultRequest(BaseModel):
    status: Literal["copied", "pasted", "sent", "blocked", "failed", "skipped"]
    pasted: bool = False
    sent: bool = False
    copied: bool = False
    reason: str = ""
    error: str = ""
    foreground_title: str = ""
    target_title: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class DesktopAgentPauseRequest(BaseModel):
    paused: bool
    platform: str = ""
    window_title: str = ""
    reason: str = ""


class DesktopAgentPauseState(BaseModel):
    platform: str = ""
    window_title: str = ""
    paused: bool = False
    reason: str = ""
    updated_at: str = ""


class DesktopAgentStateResponse(BaseModel):
    sessions: list[DesktopAgentSessionItem] = Field(default_factory=list)
    pauses: list[DesktopAgentPauseState] = Field(default_factory=list)
    recent_actions: list[dict[str, Any]] = Field(default_factory=list)


def ensure_desktop_agent_tables() -> None:
    if db_driver() == "mysql":
        ensure_mysql_tables()
        return
    ensure_sqlite_tables()


def ensure_sqlite_column(conn: Any, table: str, column: str, definition: str) -> None:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    names = {str(row[1]) for row in rows}
    if column not in names:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def ensure_mysql_column(conn: Any, table: str, column: str, definition: str) -> None:
    rows = conn.execute(f"SHOW COLUMNS FROM {table} LIKE {param()} ", (column,)).fetchall()
    if not rows:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def ensure_sqlite_tables() -> None:
    with db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS desktop_agent_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL UNIQUE,
                merchant_id INTEGER NOT NULL,
                device_name TEXT DEFAULT '',
                os_name TEXT DEFAULT '',
                platform TEXT DEFAULT 'auto',
                app_version TEXT DEFAULT '',
                mode TEXT DEFAULT 'assist',
                paused INTEGER DEFAULT 0,
                auto_send_confirmed INTEGER DEFAULT 0,
                window_allowlist_json TEXT DEFAULT '[]',
                capabilities_json TEXT DEFAULT '[]',
                metadata_json TEXT DEFAULT '{}',
                last_heartbeat_at TEXT DEFAULT '',
                created_at TEXT DEFAULT '',
                updated_at TEXT DEFAULT ''
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS desktop_agent_pause_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                merchant_id INTEGER NOT NULL,
                platform TEXT DEFAULT '',
                window_title TEXT DEFAULT '',
                paused INTEGER DEFAULT 0,
                reason TEXT DEFAULT '',
                created_at TEXT DEFAULT '',
                updated_at TEXT DEFAULT ''
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS desktop_agent_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                merchant_id INTEGER NOT NULL,
                platform TEXT DEFAULT 'auto',
                channel TEXT DEFAULT '',
                window_title TEXT DEFAULT '',
                window_id TEXT DEFAULT '',
                source TEXT DEFAULT 'unknown',
                message_hash TEXT NOT NULL,
                message_excerpt TEXT DEFAULT '',
                message_text TEXT DEFAULT '',
                status TEXT DEFAULT 'received',
                metadata_json TEXT DEFAULT '{}',
                created_at TEXT DEFAULT ''
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS desktop_agent_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_id TEXT NOT NULL UNIQUE,
                event_id INTEGER,
                session_id TEXT NOT NULL,
                merchant_id INTEGER NOT NULL,
                action TEXT DEFAULT 'none',
                mode TEXT DEFAULT 'assist',
                reply_text TEXT DEFAULT '',
                risk_flags_json TEXT DEFAULT '[]',
                intent_score INTEGER DEFAULT 0,
                workflow_run_ids_json TEXT DEFAULT '[]',
                reply_meta_json TEXT DEFAULT '{}',
                status TEXT DEFAULT 'pending',
                result_json TEXT DEFAULT '{}',
                reason TEXT DEFAULT '',
                created_at TEXT DEFAULT '',
                updated_at TEXT DEFAULT ''
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_desktop_events_lookup ON desktop_agent_events (merchant_id, session_id, message_hash)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_desktop_actions_event ON desktop_agent_actions (event_id)")
        ensure_sqlite_column(conn, "desktop_agent_actions", "reply_meta_json", "TEXT DEFAULT '{}'")


def ensure_mysql_tables() -> None:
    with db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS desktop_agent_sessions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                session_id VARCHAR(80) NOT NULL UNIQUE,
                merchant_id INT NOT NULL,
                device_name VARCHAR(160) DEFAULT '',
                os_name VARCHAR(80) DEFAULT '',
                platform VARCHAR(80) DEFAULT 'auto',
                app_version VARCHAR(80) DEFAULT '',
                mode VARCHAR(32) DEFAULT 'assist',
                paused TINYINT DEFAULT 0,
                auto_send_confirmed TINYINT DEFAULT 0,
                window_allowlist_json MEDIUMTEXT,
                capabilities_json MEDIUMTEXT,
                metadata_json MEDIUMTEXT,
                last_heartbeat_at VARCHAR(40) DEFAULT '',
                created_at VARCHAR(40) DEFAULT '',
                updated_at VARCHAR(40) DEFAULT ''
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS desktop_agent_pause_state (
                id INT AUTO_INCREMENT PRIMARY KEY,
                merchant_id INT NOT NULL,
                platform VARCHAR(80) DEFAULT '',
                window_title VARCHAR(255) DEFAULT '',
                paused TINYINT DEFAULT 0,
                reason TEXT,
                created_at VARCHAR(40) DEFAULT '',
                updated_at VARCHAR(40) DEFAULT ''
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS desktop_agent_events (
                id INT AUTO_INCREMENT PRIMARY KEY,
                session_id VARCHAR(80) NOT NULL,
                merchant_id INT NOT NULL,
                platform VARCHAR(80) DEFAULT 'auto',
                channel VARCHAR(80) DEFAULT '',
                window_title VARCHAR(255) DEFAULT '',
                window_id VARCHAR(160) DEFAULT '',
                source VARCHAR(32) DEFAULT 'unknown',
                message_hash VARCHAR(80) NOT NULL,
                message_excerpt TEXT,
                message_text MEDIUMTEXT,
                status VARCHAR(32) DEFAULT 'received',
                metadata_json MEDIUMTEXT,
                created_at VARCHAR(40) DEFAULT '',
                KEY idx_desktop_events_lookup (merchant_id, session_id, message_hash)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS desktop_agent_actions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                action_id VARCHAR(80) NOT NULL UNIQUE,
                event_id INT,
                session_id VARCHAR(80) NOT NULL,
                merchant_id INT NOT NULL,
                action VARCHAR(32) DEFAULT 'none',
                mode VARCHAR(32) DEFAULT 'assist',
                reply_text MEDIUMTEXT,
                risk_flags_json MEDIUMTEXT,
                intent_score INT DEFAULT 0,
                workflow_run_ids_json MEDIUMTEXT,
                reply_meta_json MEDIUMTEXT,
                status VARCHAR(32) DEFAULT 'pending',
                result_json MEDIUMTEXT,
                reason TEXT,
                created_at VARCHAR(40) DEFAULT '',
                updated_at VARCHAR(40) DEFAULT '',
                KEY idx_desktop_actions_event (event_id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """
        )
        ensure_mysql_column(conn, "desktop_agent_actions", "reply_meta_json", "MEDIUMTEXT")


def json_loads_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if not value:
        return []
    try:
        loaded = json.loads(str(value))
    except json.JSONDecodeError:
        return []
    return loaded if isinstance(loaded, list) else []


def json_loads_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        loaded = json.loads(str(value))
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def bool_from_db(value: Any) -> bool:
    return bool(int(value or 0))


def message_hash_for(text: str) -> str:
    normalized = " ".join(text.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def session_from_row(row: dict[str, Any]) -> DesktopAgentSessionItem:
    return DesktopAgentSessionItem(
        session_id=str(row.get("session_id") or ""),
        merchant_id=int(row.get("merchant_id") or 0),
        device_name=str(row.get("device_name") or ""),
        os_name=str(row.get("os_name") or ""),
        platform=str(row.get("platform") or "auto"),
        app_version=str(row.get("app_version") or ""),
        mode=str(row.get("mode") or "assist"),  # type: ignore[arg-type]
        paused=bool_from_db(row.get("paused")),
        auto_send_confirmed=bool_from_db(row.get("auto_send_confirmed")),
        window_allowlist=[str(item) for item in json_loads_list(row.get("window_allowlist_json"))],
        capabilities=[str(item) for item in json_loads_list(row.get("capabilities_json"))],
        last_heartbeat_at=str(row.get("last_heartbeat_at") or ""),
        created_at=str(row.get("created_at") or ""),
        updated_at=str(row.get("updated_at") or ""),
    )


def pause_from_row(row: dict[str, Any]) -> DesktopAgentPauseState:
    return DesktopAgentPauseState(
        platform=str(row.get("platform") or ""),
        window_title=str(row.get("window_title") or ""),
        paused=bool_from_db(row.get("paused")),
        reason=str(row.get("reason") or ""),
        updated_at=str(row.get("updated_at") or ""),
    )


def get_session_row(session_id: str, merchant_id: int) -> dict[str, Any] | None:
    marker = param()
    with db() as conn:
        row = conn.execute(
            f"SELECT * FROM desktop_agent_sessions WHERE merchant_id={marker} AND session_id={marker}",
            (merchant_id, session_id),
        ).fetchone()
    return dict(row) if row else None


def pause_active(merchant_id: int, platform: str = "", window_title: str = "") -> tuple[bool, str]:
    marker = param()
    with db() as conn:
        rows = rows_to_dicts(
            conn.execute(
                f"""
                SELECT * FROM desktop_agent_pause_state
                WHERE merchant_id={marker} AND paused=1
                ORDER BY id DESC
                """,
                (merchant_id,),
            ).fetchall()
        )
    for row in rows:
        pause_platform = str(row.get("platform") or "")
        pause_window = str(row.get("window_title") or "")
        if pause_platform and pause_platform != platform:
            continue
        if pause_window and pause_window != window_title:
            continue
        return True, str(row.get("reason") or "paused by operator")
    return False, ""


async def register_desktop_agent_session(payload: DesktopAgentSessionRequest, merchant: MerchantProfile) -> DesktopAgentSessionResponse:
    ensure_desktop_agent_tables()
    marker = param()
    session_id = payload.session_id.strip() or f"desktop-{uuid.uuid4()}"
    now = now_sql()
    device_name = payload.device_name.strip() or socket.gethostname()
    os_name = payload.os_name.strip()
    paused_by_state, pause_reason = pause_active(merchant.id or 0, payload.platform, "")
    paused = payload.paused or payload.mode == "paused" or paused_by_state
    mode: DesktopAgentMode = "paused" if paused else payload.mode
    existing = get_session_row(session_id, merchant.id or 0)
    with db() as conn:
        if existing:
            conn.execute(
                f"""
                UPDATE desktop_agent_sessions
                SET device_name={marker}, os_name={marker}, platform={marker}, app_version={marker},
                    mode={marker}, paused={marker}, auto_send_confirmed={marker},
                    window_allowlist_json={marker}, capabilities_json={marker}, metadata_json={marker},
                    last_heartbeat_at={marker}, updated_at={marker}
                WHERE merchant_id={marker} AND session_id={marker}
                """,
                (
                    device_name,
                    os_name,
                    payload.platform,
                    payload.app_version,
                    mode,
                    1 if paused else 0,
                    1 if payload.auto_send_confirmed else 0,
                    json.dumps(payload.window_allowlist, ensure_ascii=False),
                    json.dumps(payload.capabilities, ensure_ascii=False),
                    json.dumps(payload.metadata, ensure_ascii=False),
                    now,
                    now,
                    merchant.id,
                    session_id,
                ),
            )
        else:
            conn.execute(
                f"""
                INSERT INTO desktop_agent_sessions (
                    session_id, merchant_id, device_name, os_name, platform, app_version, mode, paused,
                    auto_send_confirmed, window_allowlist_json, capabilities_json, metadata_json,
                    last_heartbeat_at, created_at, updated_at
                )
                VALUES ({marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker})
                """,
                (
                    session_id,
                    merchant.id,
                    device_name,
                    os_name,
                    payload.platform,
                    payload.app_version,
                    mode,
                    1 if paused else 0,
                    1 if payload.auto_send_confirmed else 0,
                    json.dumps(payload.window_allowlist, ensure_ascii=False),
                    json.dumps(payload.capabilities, ensure_ascii=False),
                    json.dumps(payload.metadata, ensure_ascii=False),
                    now,
                    now,
                    now,
                ),
            )
    row = get_session_row(session_id, merchant.id or 0)
    if not row:
        raise HTTPException(status_code=500, detail="Desktop agent session was not saved")
    session = session_from_row(row)
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "desktop_agent.session.start",
        "desktop_agent_session",
        session.session_id,
        "Desktop agent session registered",
        {"platform": session.platform, "mode": session.mode, "paused": session.paused, "reason": pause_reason},
    )
    return DesktopAgentSessionResponse(
        session=session,
        paused=session.paused,
        effective_mode=session.mode,
        next_action="resume before reading windows" if session.paused else "agent can listen",
    )


def latest_action_for_event(event_id: int, merchant_id: int) -> dict[str, Any] | None:
    marker = param()
    with db() as conn:
        row = conn.execute(
            f"""
            SELECT * FROM desktop_agent_actions
            WHERE merchant_id={marker} AND event_id={marker}
            ORDER BY id DESC
            """,
            (merchant_id, event_id),
        ).fetchone()
    return dict(row) if row else None


def decision_from_existing_action(event_row: dict[str, Any], action_row: dict[str, Any]) -> DesktopAgentDecision:
    return DesktopAgentDecision(
        event_id=int(event_row.get("id") or 0),
        action_id=str(action_row.get("action_id") or ""),
        session_id=str(event_row.get("session_id") or ""),
        action=str(action_row.get("action") or "none"),  # type: ignore[arg-type]
        should_reply=str(action_row.get("action") or "") in {"draft_only", "paste_reply", "send_reply"},
        reply_text=str(action_row.get("reply_text") or ""),
        risk_flags=[str(item) for item in json_loads_list(action_row.get("risk_flags_json"))],
        intent_score=int(action_row.get("intent_score") or 0),
        mode=str(action_row.get("mode") or "assist"),  # type: ignore[arg-type]
        idempotent=True,
        message_hash=str(event_row.get("message_hash") or ""),
        workflow_run_ids=[str(item) for item in json_loads_list(action_row.get("workflow_run_ids_json"))],
        reason=str(action_row.get("reason") or "duplicate message hash"),
        reply_meta=json_loads_dict(action_row.get("reply_meta_json", "{}")),
    )


def find_existing_event(session_id: str, merchant_id: int, message_hash: str) -> dict[str, Any] | None:
    marker = param()
    with db() as conn:
        row = conn.execute(
            f"""
            SELECT * FROM desktop_agent_events
            WHERE merchant_id={marker} AND session_id={marker} AND message_hash={marker}
            ORDER BY id DESC
            """,
            (merchant_id, session_id, message_hash),
        ).fetchone()
    return dict(row) if row else None


def insert_event(payload: DesktopAgentEventRequest, merchant_id: int, message_hash: str, status: str) -> int:
    marker = param()
    now = now_sql()
    with db() as conn:
        cursor = conn.execute(
            f"""
            INSERT INTO desktop_agent_events (
                session_id, merchant_id, platform, channel, window_title, window_id, source,
                message_hash, message_excerpt, message_text, status, metadata_json, created_at
            )
            VALUES ({marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker})
            """,
            (
                payload.session_id,
                merchant_id,
                payload.platform,
                payload.channel,
                payload.window_title,
                payload.window_id,
                payload.source,
                message_hash,
                payload.message_text[:500],
                payload.message_text,
                status,
                json.dumps(payload.metadata, ensure_ascii=False),
                now,
            ),
        )
        return int(cursor.lastrowid)


def insert_action(
    *,
    event_id: int,
    session_id: str,
    merchant_id: int,
    action: DesktopAgentAction,
    mode: DesktopAgentMode,
    reply_text: str,
    risk_flags: list[str],
    intent_score: int,
    workflow_run_ids: list[str],
    reply_meta: dict[str, Any] | None = None,
    status: str,
    reason: str,
) -> str:
    marker = param()
    action_id = f"desktop-action-{uuid.uuid4()}"
    now = now_sql()
    with db() as conn:
        conn.execute(
            f"""
            INSERT INTO desktop_agent_actions (
                action_id, event_id, session_id, merchant_id, action, mode, reply_text,
                risk_flags_json, intent_score, workflow_run_ids_json, reply_meta_json, status, result_json, reason,
                created_at, updated_at
            )
            VALUES ({marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker})
            """,
            (
                action_id,
                event_id,
                session_id,
                merchant_id,
                action,
                mode,
                reply_text,
                json.dumps(risk_flags, ensure_ascii=False),
                intent_score,
                json.dumps(workflow_run_ids, ensure_ascii=False),
                json.dumps(reply_meta or {}, ensure_ascii=False),
                status,
                "{}",
                reason,
                now,
                now,
            ),
        )
    return action_id


def update_action_workflow_runs(action_id: str, merchant_id: int, workflow_run_ids: list[str]) -> None:
    marker = param()
    with db() as conn:
        conn.execute(
            f"""
            UPDATE desktop_agent_actions
            SET workflow_run_ids_json={marker}, updated_at={marker}
            WHERE merchant_id={marker} AND action_id={marker}
            """,
            (json.dumps(workflow_run_ids, ensure_ascii=False), now_sql(), merchant_id, action_id),
        )


def build_reply_prompt(merchant: MerchantProfile, payload: DesktopAgentEventRequest, knowledge: str, citations: list[dict[str, Any]] | None = None) -> str:
    pieces = [
        "You are the merchant's AI customer-service assistant.",
        "Reply in the customer's language. Be concise, grounded, and commercially helpful.",
        "Do not promise refunds, compensation, delivery guarantees, account fixes, or legal/financial outcomes.",
        "Ask for missing purchase or lead information only when it naturally helps the next step.",
        f"Business name: {merchant.business_name or merchant.username}",
        f"Industry: {merchant.industry}",
        f"Products/services: {merchant.products_services}",
        f"Pricing: {merchant.pricing}",
        f"Promotions: {merchant.promotions}",
        f"Hours: {merchant.hours}",
        f"Contact: {merchant.contact}",
    ]
    if payload.merchant_profile:
        pieces.append(f"Desktop operator profile:\n{payload.merchant_profile[:3000]}")
    if citations:
        citation_lines = []
        for item in citations:
            citation_lines.append(
                f"[source:{item.get('id')}] {item.get('title')} ({item.get('source_type')}): {str(item.get('snippet') or '')}"
            )
        pieces.append("Use only these matched knowledge sources when answering:\n" + "\n".join(citation_lines))
    elif knowledge:
        pieces.append(
            "No directly matched knowledge source was found for this message. "
            "If the answer requires product, price, policy, invoice, contract, delivery, or after-sale facts, say it needs human confirmation."
        )
        pieces.append(f"General knowledge base context, not a citation:\n{knowledge[:3000]}")
    if payload.reply_goal:
        pieces.append(f"Reply goal: {payload.reply_goal[:800]}")
    return "\n\n".join(piece for piece in pieces if str(piece).strip())


def fallback_reply_for(merchant: MerchantProfile, message: str) -> str:
    product = merchant.products_services or merchant.business_intro or "our service"
    return (
        f"您好，您问的这个我先按当前资料给您确认：{product}。\n"
        "如果您方便的话，可以补充一下具体需求、预算或使用场景，我这边就能更准确地给您推荐下一步。"
    )


def fallback_reply_for(merchant: MerchantProfile, message: str) -> str:
    product = merchant.products_services or merchant.business_intro or "our service"
    return (
        f"\u60a8\u597d\uff0c\u6211\u5148\u6839\u636e\u5f53\u524d\u4f01\u4e1a\u8d44\u6599\u5e2e\u60a8\u786e\u8ba4\uff1a{product}\u3002"
        "\u5982\u679c\u6d89\u53ca\u4ef7\u683c\u3001\u5408\u540c\u3001\u53d1\u7968\u3001\u552e\u540e\u3001\u9000\u6b3e\u6216\u627f\u8bfa\u4e8b\u9879\uff0c"
        "\u9700\u8981\u4eba\u5de5\u5ba2\u670d\u786e\u8ba4\uff0c\u6211\u5e2e\u60a8\u8f6c\u63a5\u3002"
    )


def extra_safety_flags(text: str) -> list[str]:
    terms = {
        "refund_or_after_sale": ["退款", "退货", "赔付", "售后", "投诉", "差评"],
        "payment": ["付款", "转账", "银行卡", "押金", "发票", "合同"],
        "account_or_privacy": ["密码", "验证码", "身份证", "手机号", "隐私", "账号"],
        "medical_or_legal": ["律师", "起诉", "报警", "医疗", "诊断"],
    }
    flags: list[str] = []
    lowered = text.lower()
    for label, words in terms.items():
        if any(word.lower() in lowered for word in words):
            flags.append(label)
    return flags


def extra_safety_flags(text: str) -> list[str]:
    terms = {
        "refund_or_after_sale": ["\u9000\u6b3e", "\u9000\u8d27", "\u552e\u540e", "\u8d54\u4ed8", "\u6295\u8bc9", "\u5dee\u8bc4", "refund", "return", "complaint"],
        "payment": ["\u4ed8\u6b3e", "\u8f6c\u8d26", "\u94f6\u884c\u5361", "\u62bc\u91d1", "\u53d1\u7968", "\u5408\u540c", "\u627f\u8bfa", "payment", "invoice", "contract", "promise"],
        "account_or_privacy": ["\u5bc6\u7801", "\u9a8c\u8bc1\u7801", "\u8eab\u4efd\u8bc1", "\u624b\u673a\u53f7", "\u9690\u79c1", "\u8d26\u53f7", "password", "verification code"],
        "medical_or_legal": ["\u5f8b\u5e08", "\u8d77\u8bc9", "\u62a5\u8b66", "\u533b\u7597", "\u8bca\u65ad", "legal", "medical"],
    }
    lowered = text.lower()
    flags: list[str] = []
    for label, words in terms.items():
        if any(word.lower() in lowered for word in words):
            flags.append(label)
    return flags


def citation_terms(text: str) -> set[str]:
    lowered = text.lower()
    terms = set(re.findall(r"[a-zA-Z0-9_+\-.]{3,}", lowered))
    for token in re.findall(r"[\u4e00-\u9fff]{2,}", text):
        terms.add(token)
        for index in range(0, max(0, len(token) - 1)):
            terms.add(token[index : index + 2])
    return {term for term in terms if len(term.strip()) >= 2}


def knowledge_citations_for(merchant_id: int | None, query: str, limit: int = 3) -> list[dict[str, Any]]:
    if not merchant_id:
        return []
    query_terms = citation_terms(query)
    if not query_terms:
        return []
    scored: list[tuple[int, dict[str, Any]]] = []
    for row in knowledge_rows(merchant_id, limit=80):
        title = str(row.get("title") or "")
        content = str(row.get("content") or "")
        row_terms = citation_terms(f"{title}\n{content}")
        score = len(query_terms.intersection(row_terms))
        if score > 0:
            scored.append((score, row))
    scored.sort(key=lambda item: (item[0], int(item[1].get("id") or 0)), reverse=True)
    citations: list[dict[str, Any]] = []
    for score, row in scored[:limit]:
        content = str(row.get("content") or "")
        citations.append(
            {
                "id": int(row.get("id") or 0),
                "title": str(row.get("title") or ""),
                "source_type": str(row.get("source_type") or ""),
                "tags": str(row.get("tags") or ""),
                "snippet": content[:260],
                "match_score": score,
            }
        )
    return citations


def confidence_for(*, parse_confidence: float, citations: list[dict[str, Any]], risk_flags: list[str]) -> float:
    confidence = max(0.05, min(0.98, parse_confidence))
    confidence += 0.12 if citations else -0.28
    if risk_flags:
        confidence -= 0.25
    return round(max(0.01, min(0.99, confidence)), 2)


def desktop_customer_key(payload: DesktopAgentEventRequest, message_hash: str) -> str:
    raw_identity = "|".join(
        [
            str(payload.platform or "desktop_agent"),
            str(payload.metadata.get("account") or ""),
            str(payload.metadata.get("contact") or ""),
            payload.window_id,
            payload.window_title,
            message_hash,
        ]
    )
    return "desktop-" + hashlib.sha256(raw_identity.encode("utf-8")).hexdigest()[:24]


def record_desktop_business_activity(
    *,
    merchant: MerchantProfile,
    payload: DesktopAgentEventRequest,
    message_hash: str,
    reply_text: str,
    intent_score: int,
    risk_flags: list[str],
    action: DesktopAgentAction,
    workflow_run_ids: list[str],
) -> int:
    merchant_id = merchant.id or 0
    contact = str(payload.metadata.get("contact") or "").strip()
    account = str(payload.metadata.get("account") or "").strip()
    visitor_id = desktop_customer_key(payload, message_hash)
    need_followup = action == "handoff" or bool(risk_flags) or intent_score >= 70
    customer_id = upsert_customer(
        merchant_id,
        visitor_id,
        payload.message_text,
        intent_score,
        need_followup,
        source_channel=payload.platform or "desktop_agent",
        session_id=payload.session_id,
        risk_flags=risk_flags,
    )
    marker = param()
    display_name = contact or account or f"{payload.platform or 'desktop'} customer"
    workflow_run_id = workflow_run_ids[0] if workflow_run_ids else ""
    visitor_info = {
        "visitor_id": visitor_id,
        "platform": payload.platform,
        "channel": payload.channel,
        "window_title": payload.window_title,
        "window_id": payload.window_id,
        "contact": contact,
        "account": account,
        "message_hash": message_hash,
    }
    with db() as conn:
        conn.execute(
            f"""
            UPDATE customers
            SET name={marker}, contact=COALESCE(NULLIF(contact, ''), {marker}), updated_at={marker}
            WHERE merchant_id={marker} AND id={marker}
            """,
            (display_name, contact or account, now_sql(), merchant_id, customer_id),
        )
        conn.execute(
            f"""
            INSERT INTO conversations (
                merchant_id, customer_id, session_id, visitor_info, query, response, intent_score,
                need_followup, source_channel, risk_flags, workflow_run_id, created_at
            )
            VALUES ({marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker})
            """,
            (
                merchant_id,
                customer_id,
                payload.session_id,
                json.dumps(visitor_info, ensure_ascii=False),
                payload.message_text,
                reply_text,
                intent_score,
                1 if need_followup else 0,
                payload.platform or "desktop_agent",
                join_tags(risk_flags),
                workflow_run_id,
                now_sql(),
            ),
        )
    if need_followup:
        ensure_followup_task(
            merchant_id,
            customer_id,
            "桌面客服高意向或人工接管跟进",
            workflow_run_id,
            payload.platform or "desktop_agent",
        )
    return customer_id


def record_desktop_sent_chat_log(action_row: dict[str, Any], merchant: MerchantProfile) -> None:
    query = str(action_row.get("message_text") or "")
    reply_text = str(action_row.get("reply_text") or "")
    if not query.strip() or not reply_text.strip():
        return
    metadata = json_loads_dict(action_row.get("event_metadata_json", "{}"))
    visitor_id = desktop_customer_key(
        DesktopAgentEventRequest(
            session_id=str(action_row.get("session_id") or ""),
            platform=str(action_row.get("platform") or "desktop_agent"),
            channel=str(action_row.get("channel") or ""),
            window_title=str(action_row.get("window_title") or ""),
            window_id=str(action_row.get("window_id") or ""),
            source=str(action_row.get("source") or "unknown"),  # type: ignore[arg-type]
            message_text=query,
            message_hash=str(action_row.get("message_hash") or ""),
            metadata=metadata,
        ),
        str(action_row.get("message_hash") or message_hash_for(query)),
    )
    marker = param()
    with db() as conn:
        conn.execute(
            f"""
            INSERT INTO chat_logs (merchant_id, bot_id, user_id, query, response, created_at)
            VALUES ({marker}, {marker}, {marker}, {marker}, {marker}, {marker})
            """,
            (merchant.id, merchant.merchant_code, visitor_id, query, reply_text, now_sql()),
        )


def choose_action(
    *,
    mode: DesktopAgentMode,
    paused: bool,
    risk_flags: list[str],
    session: DesktopAgentSessionItem,
    payload: DesktopAgentEventRequest,
    reply_text: str,
) -> tuple[DesktopAgentAction, bool, str, dict[str, Any]]:
    checks = {
        "mode": mode,
        "paused": paused,
        "risk_clear": not risk_flags,
        "session_auto_send_confirmed": session.auto_send_confirmed,
        "event_auto_send_enabled": payload.auto_send_enabled,
        "event_confirm_phrase_ok": payload.auto_send_confirm_phrase == CONFIRM_DESKTOP_AUTO_SEND,
        "has_reply": bool(reply_text.strip()),
    }
    if paused:
        return "none", False, "paused", checks
    if not reply_text.strip():
        return "none", False, "empty reply", checks
    if risk_flags:
        return "handoff", False, "risk flags require human handoff", checks
    if mode == "auto_send":
        if session.auto_send_confirmed and payload.auto_send_enabled and payload.auto_send_confirm_phrase == CONFIRM_DESKTOP_AUTO_SEND:
            return "send_reply", True, "safe auto-send action", checks
        return "paste_reply", True, "auto-send not fully confirmed; downgraded to paste", checks
    if mode == "auto_paste":
        return "paste_reply", True, "auto-paste mode", checks
    return "draft_only", True, "assist mode", checks


async def ingest_desktop_agent_event(payload: DesktopAgentEventRequest, merchant: MerchantProfile) -> DesktopAgentDecision:
    ensure_desktop_agent_tables()
    row = get_session_row(payload.session_id, merchant.id or 0)
    if not row:
        raise HTTPException(status_code=404, detail="Desktop agent session not found")
    session = session_from_row(row)
    marker = param()
    now = now_sql()
    with db() as conn:
        conn.execute(
            f"UPDATE desktop_agent_sessions SET last_heartbeat_at={marker}, updated_at={marker} WHERE merchant_id={marker} AND session_id={marker}",
            (now, now, merchant.id, payload.session_id),
        )
    message_hash = payload.message_hash.strip() or message_hash_for(payload.message_text)
    existing_event = find_existing_event(payload.session_id, merchant.id or 0, message_hash)
    if existing_event:
        existing_action = latest_action_for_event(int(existing_event.get("id") or 0), merchant.id or 0)
        if existing_action:
            return decision_from_existing_action(existing_event, existing_action)

    requested_mode: DesktopAgentMode = payload.mode or session.mode
    paused_by_state, pause_reason = pause_active(merchant.id or 0, payload.platform or session.platform, payload.window_title)
    paused = payload.local_paused or session.paused or requested_mode == "paused" or paused_by_state
    mode: DesktopAgentMode = "paused" if paused else requested_mode
    event_id = insert_event(payload, merchant.id or 0, message_hash, "paused" if paused else "received")
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "desktop_agent.message.read",
        "desktop_agent_event",
        str(event_id),
        "Desktop agent read a customer-service window message",
        {
            "session_id": payload.session_id,
            "platform": payload.platform,
            "source": payload.source,
            "window_title": payload.window_title,
            "message_hash": message_hash,
            "paused": paused,
        },
    )
    if paused:
        action_id = insert_action(
            event_id=event_id,
            session_id=payload.session_id,
            merchant_id=merchant.id or 0,
            action="none",
            mode="paused",
            reply_text="",
            risk_flags=[],
            intent_score=0,
            workflow_run_ids=[],
            status="skipped",
            reason=pause_reason or "paused",
        )
        return DesktopAgentDecision(
            event_id=event_id,
            action_id=action_id,
            session_id=payload.session_id,
            action="none",
            mode="paused",
            paused=True,
            message_hash=message_hash,
            reason=pause_reason or "paused",
            safety_checks={"paused": True},
        )

    engine = default_ai_engine(DATA_DIR)
    connector_safety = json_loads_dict(payload.metadata.get("connector_safety", {}))
    connector_risks = [str(item) for item in connector_safety.get("risk_flags", []) if item]
    risk = engine.assess_risk(payload.message_text)
    citations = knowledge_citations_for(merchant.id, payload.message_text)
    risk_flags = list(dict.fromkeys([*risk.risk_flags, *extra_safety_flags(payload.message_text), *connector_risks]))
    if not citations:
        risk_flags = list(dict.fromkeys([*risk_flags, "knowledge_no_answer"]))
    intent = engine.score_intent(payload.message_text)
    knowledge = knowledge_context_for(merchant.id)
    system_prompt = build_reply_prompt(merchant, payload, knowledge, citations)
    fallback = fallback_reply_for(merchant, payload.message_text)
    reply = engine.generate_reply(
        system_prompt=system_prompt,
        user_message=payload.message_text,
        history=[],
        fallback_text=fallback,
        temperature=0.45,
        timeout=35,
    )
    reply_text = reply.text.strip() or fallback
    if not citations:
        reply_text = "这个问题需要人工客服确认，我帮您转接。"
    parse_confidence = float(payload.metadata.get("parse_confidence") or 0.7)
    reply_meta = {
        "connector": payload.metadata.get("connector") or payload.platform,
        "contact": payload.metadata.get("contact") or "",
        "account": payload.metadata.get("account") or "",
        "ai_mode": reply.mode,
        "ai_model": engine.chat_config().model,
        "confidence": confidence_for(parse_confidence=parse_confidence, citations=citations, risk_flags=risk_flags),
        "citations": citations,
        "connector_safety": connector_safety,
        "knowledge_answered": bool(citations),
    }
    action, should_reply, reason, checks = choose_action(
        mode=mode,
        paused=False,
        risk_flags=risk_flags,
        session=session,
        payload=payload,
        reply_text=reply_text,
    )
    status = "blocked" if action == "handoff" else "pending"
    action_id = insert_action(
        event_id=event_id,
        session_id=payload.session_id,
        merchant_id=merchant.id or 0,
        action=action,
        mode=mode,
        reply_text=reply_text,
        risk_flags=risk_flags,
        intent_score=intent.score,
        workflow_run_ids=[],
        reply_meta=reply_meta,
        status=status,
        reason=reason,
    )
    workflow_payload = {
        "message": payload.message_text,
        "event_id": event_id,
        "action_id": action_id,
        "session_id": payload.session_id,
        "source": "desktop_auto_reply",
        "platform": payload.platform,
        "channel": payload.channel or payload.platform,
        "window_title": payload.window_title,
        "message_hash": message_hash,
        "intent_score": intent.score,
        "risk_flags": risk_flags,
        "knowledge_chars": len(knowledge),
        "reply_text": reply_text,
        "action": action,
        "should_reply": should_reply,
        "auto_send_enabled": payload.auto_send_enabled,
        "auto_send_confirmed": session.auto_send_confirmed and payload.auto_send_confirm_phrase == CONFIRM_DESKTOP_AUTO_SEND,
        "reason": reason,
        "reply_meta": reply_meta,
    }
    workflow_runs = workflow_engine.trigger("message", "desktop_auto_reply", workflow_payload)
    workflow_run_ids = [run.id for run in workflow_runs]
    update_action_workflow_runs(action_id, merchant.id or 0, workflow_run_ids)
    customer_id = record_desktop_business_activity(
        merchant=merchant,
        payload=payload,
        message_hash=message_hash,
        reply_text=reply_text,
        intent_score=intent.score,
        risk_flags=risk_flags,
        action=action,
        workflow_run_ids=workflow_run_ids,
    )
    record_usage(merchant.id or 0, "desktop_agent_event", 1, payload.platform, payload.session_id, {"action": action, "mode": mode})
    record_usage(merchant.id or 0, "ai_reply", 1, "desktop_agent", action_id, {"mode": reply.mode, "risk_flags": risk_flags})
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "desktop_agent.reply.generated" if should_reply else "desktop_agent.reply.blocked",
        "desktop_agent_action",
        action_id,
        "Desktop agent generated a guarded AI reply",
        {
            "event_id": event_id,
            "action": action,
            "mode": mode,
            "risk_flags": risk_flags,
            "intent_score": intent.score,
            "workflow_run_ids": workflow_run_ids,
            "reason": reason,
            "reply_meta": reply_meta,
            "customer_id": customer_id,
        },
    )
    return DesktopAgentDecision(
        event_id=event_id,
        action_id=action_id,
        session_id=payload.session_id,
        action=action,
        should_reply=should_reply,
        reply_text=reply_text,
        risk_flags=risk_flags,
        intent_score=intent.score,
        mode=mode,
        paused=False,
        message_hash=message_hash,
        workflow_run_ids=workflow_run_ids,
        reason=reason,
        safety_checks=checks,
        reply_meta=reply_meta,
    )


async def record_desktop_agent_action_result(
    action_id: str,
    payload: DesktopAgentActionResultRequest,
    merchant: MerchantProfile,
) -> dict[str, Any]:
    ensure_desktop_agent_tables()
    marker = param()
    with db() as conn:
        row = conn.execute(
            f"""
            SELECT a.*, e.message_text, e.platform, e.channel, e.window_title, e.window_id,
                   e.source, e.message_hash, e.metadata_json AS event_metadata_json
            FROM desktop_agent_actions a
            LEFT JOIN desktop_agent_events e ON e.id = a.event_id
            WHERE a.merchant_id={marker} AND a.action_id={marker}
            """,
            (merchant.id, action_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Desktop agent action not found")
        action_row = dict(row)
        conn.execute(
            f"""
            UPDATE desktop_agent_actions
            SET status={marker}, result_json={marker}, updated_at={marker}
            WHERE merchant_id={marker} AND action_id={marker}
            """,
            (
                payload.status,
                json.dumps(payload.model_dump(), ensure_ascii=False),
                now_sql(),
                merchant.id,
                action_id,
            ),
        )
    if payload.sent and str(action_row.get("action") or "") == "send_reply":
        record_desktop_sent_chat_log(action_row, merchant)
    audit_action = "desktop_agent.reply.sent" if payload.sent else "desktop_agent.reply.pasted" if payload.pasted else "desktop_agent.reply.blocked"
    if payload.status == "failed":
        audit_action = "desktop_agent.error"
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        audit_action,
        "desktop_agent_action",
        action_id,
        "Desktop agent action result recorded",
        {"status": payload.status, "action": action_row.get("action"), **payload.model_dump()},
    )
    return {"action_id": action_id, "status": payload.status, "recorded": True}


async def update_desktop_agent_pause(payload: DesktopAgentPauseRequest, merchant: MerchantProfile) -> DesktopAgentPauseState:
    ensure_desktop_agent_tables()
    marker = param()
    now = now_sql()
    with db() as conn:
        row = conn.execute(
            f"""
            SELECT * FROM desktop_agent_pause_state
            WHERE merchant_id={marker} AND platform={marker} AND window_title={marker}
            ORDER BY id DESC
            """,
            (merchant.id, payload.platform, payload.window_title),
        ).fetchone()
        if row:
            conn.execute(
                f"""
                UPDATE desktop_agent_pause_state
                SET paused={marker}, reason={marker}, updated_at={marker}
                WHERE merchant_id={marker} AND platform={marker} AND window_title={marker}
                """,
                (1 if payload.paused else 0, payload.reason, now, merchant.id, payload.platform, payload.window_title),
            )
        else:
            conn.execute(
                f"""
                INSERT INTO desktop_agent_pause_state (merchant_id, platform, window_title, paused, reason, created_at, updated_at)
                VALUES ({marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker})
                """,
                (merchant.id, payload.platform, payload.window_title, 1 if payload.paused else 0, payload.reason, now, now),
            )
        session_updates = [f"paused={marker}", f"updated_at={marker}"]
        params: list[Any] = [1 if payload.paused else 0, now, merchant.id]
        where = [f"merchant_id={marker}"]
        if payload.platform:
            where.append(f"platform={marker}")
            params.append(payload.platform)
        conn.execute(f"UPDATE desktop_agent_sessions SET {', '.join(session_updates)} WHERE {' AND '.join(where)}", tuple(params))
        updated = conn.execute(
            f"""
            SELECT * FROM desktop_agent_pause_state
            WHERE merchant_id={marker} AND platform={marker} AND window_title={marker}
            ORDER BY id DESC
            """,
            (merchant.id, payload.platform, payload.window_title),
        ).fetchone()
    state = pause_from_row(dict(updated))
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "desktop_agent.paused" if payload.paused else "desktop_agent.resumed",
        "desktop_agent_pause",
        payload.platform or "all",
        "Desktop agent pause state changed",
        {"platform": payload.platform, "window_title": payload.window_title, "reason": payload.reason},
    )
    return state


async def desktop_agent_state(merchant: MerchantProfile) -> DesktopAgentStateResponse:
    ensure_desktop_agent_tables()
    marker = param()
    with db() as conn:
        sessions = rows_to_dicts(
            conn.execute(
                f"SELECT * FROM desktop_agent_sessions WHERE merchant_id={marker} ORDER BY updated_at DESC, id DESC LIMIT 20",
                (merchant.id,),
            ).fetchall()
        )
        pauses = rows_to_dicts(
            conn.execute(
                f"SELECT * FROM desktop_agent_pause_state WHERE merchant_id={marker} ORDER BY updated_at DESC, id DESC LIMIT 20",
                (merchant.id,),
            ).fetchall()
        )
        actions = rows_to_dicts(
            conn.execute(
                f"""
                SELECT a.*, e.platform, e.window_title, e.source, e.message_hash, e.message_excerpt
                FROM desktop_agent_actions a
                LEFT JOIN desktop_agent_events e ON e.id = a.event_id
                WHERE a.merchant_id={marker}
                ORDER BY a.id DESC
                LIMIT 20
                """,
                (merchant.id,),
            ).fetchall()
        )
    for action in actions:
        action["risk_flags"] = json_loads_list(action.pop("risk_flags_json", "[]"))
        action["workflow_run_ids"] = json_loads_list(action.pop("workflow_run_ids_json", "[]"))
        action["reply_meta"] = json_loads_dict(action.pop("reply_meta_json", "{}"))
        action["result"] = json_loads_dict(action.pop("result_json", "{}"))
        action["reply_text"] = str(action.get("reply_text") or "")[:500]
    return DesktopAgentStateResponse(
        sessions=[session_from_row(row) for row in sessions],
        pauses=[pause_from_row(row) for row in pauses],
        recent_actions=actions,
    )


async def desktop_agent_logs(merchant: MerchantProfile, limit: int = 50) -> list[dict[str, Any]]:
    ensure_desktop_agent_tables()
    marker = param()
    safe_limit = max(1, min(int(limit), 200))
    with db() as conn:
        rows = rows_to_dicts(
            conn.execute(
                f"""
                SELECT a.*, e.platform, e.channel, e.window_title, e.source, e.message_hash, e.message_excerpt, e.created_at AS event_created_at
                FROM desktop_agent_actions a
                LEFT JOIN desktop_agent_events e ON e.id = a.event_id
                WHERE a.merchant_id={marker}
                ORDER BY a.id DESC
                LIMIT {safe_limit}
                """,
                (merchant.id,),
            ).fetchall()
        )
    for row in rows:
        row["risk_flags"] = json_loads_list(row.pop("risk_flags_json", "[]"))
        row["workflow_run_ids"] = json_loads_list(row.pop("workflow_run_ids_json", "[]"))
        row["reply_meta"] = json_loads_dict(row.pop("reply_meta_json", "{}"))
        row["result"] = json_loads_dict(row.pop("result_json", "{}"))
        row["reply_text"] = str(row.get("reply_text") or "")[:1200]
    return rows
