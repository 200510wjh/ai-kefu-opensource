from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Enterprise(BaseModel):
    id: str
    name: str
    industry: str = ""
    owner_user_id: str = ""


class User(BaseModel):
    id: str
    enterprise_id: str
    name: str
    role: Literal["owner", "operations_lead", "service_lead", "agent", "admin"] = "agent"


class Lead(BaseModel):
    id: str
    enterprise_id: str
    source_connector: str
    name: str = ""
    contact: str = ""
    need: str = ""
    status: Literal["new", "pending", "needs_followup", "qualified", "converted", "invalid"] = "new"
    sales_stage: Literal["new", "contacted", "high_intent", "follow_up", "quoted", "won", "lost"] = "new"
    owner_user_id: str = ""
    intent_score: int = 0
    tags: list[str] = Field(default_factory=list)
    next_followup_at: str = ""
    notes: str = ""


class Customer(BaseModel):
    id: str
    enterprise_id: str
    name: str
    contact: str = ""
    source_connector: str = ""
    sales_status: Literal["new", "contacted", "high_intent", "quoted", "won", "lost"] = "new"
    owner_user_id: str = ""
    intent_score: int = 0
    tags: list[str] = Field(default_factory=list)
    profile: dict[str, Any] = Field(default_factory=dict)


class Conversation(BaseModel):
    id: str
    enterprise_id: str
    customer_id: str = ""
    connector: str = "website"
    status: Literal["open", "handoff", "archived"] = "open"
    source_channel: str = ""
    intent_score: int = 0
    risk_flags: list[str] = Field(default_factory=list)


class FollowUpTask(BaseModel):
    id: str
    enterprise_id: str
    target_type: Literal["lead", "customer", "conversation"] = "lead"
    target_id: str
    title: str
    status: Literal["open", "done", "cancelled"] = "open"
    priority: Literal["low", "normal", "high"] = "normal"
    owner_user_id: str = ""
    due_at: str = ""
    workflow_run_id: str = ""


class Message(BaseModel):
    id: str
    conversation_id: str
    role: Literal["customer", "assistant", "agent", "system"]
    content: str
    connector_message_id: str = ""


class KnowledgeItem(BaseModel):
    id: str
    enterprise_id: str
    title: str
    content: str
    version: int = 1
    tags: list[str] = Field(default_factory=list)


class Product(BaseModel):
    id: str
    enterprise_id: str
    name: str
    category: str = ""
    selling_points: list[str] = Field(default_factory=list)
    faq_ids: list[str] = Field(default_factory=list)


class AiDecision(BaseModel):
    id: str
    enterprise_id: str
    target_type: Literal["lead", "customer", "conversation", "product", "channel", "workflow"]
    target_id: str
    decision_type: Literal["intent_score", "risk", "summary", "recommendation"]
    result: dict[str, Any] = Field(default_factory=dict)


class Report(BaseModel):
    id: str
    enterprise_id: str
    report_type: Literal["daily", "weekly", "monthly", "service_quality", "acquisition", "crm"]
    title: str
    content: str
