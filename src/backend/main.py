"""
AI客服后端服务 - FastAPI
对接扣子(Coze) API实现智能客服
"""
import asyncio
import hashlib
import hmac
import json
import time
from datetime import datetime
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx

# ============== 配置 ==============
COZE_API_URL = "https://api.coze.cn/v1/chat"
COZE_BOT_ID = "7631125644738379811"
COZE_API_KEY = "pat_KaeGWcFwKM6WsXOLyiOypKvqn4gXwjPGyf6zNISlqTwAMQaS6z0gBkx24C5tbHun"

app = FastAPI(title="AI客服后端", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============== 数据模型 ==============
class Message(BaseModel):
    platform: str  # dy_feige, tb_qianiu, douyin, etc.
    user_id: str
    content: str
    order_no: Optional[str] = None
    goods_info: Optional[Dict[str, Any]] = None

class ChatRequest(BaseModel):
    message: str
    user_id: str
    platform: str
    order_no: Optional[str] = None
    goods_info: Optional[Dict[str, Any]] = None

class ChatResponse(BaseModel):
    code: int
    msg: str
    data: Optional[Dict[str, Any]] = None

# ============== 扣子API对接 ==============
async def call_coze_api(user_message: str, user_id: str, platform: str) -> Dict[str, Any]:
    """调用扣子API获取AI回复"""
    headers = {
        "Authorization": f"Bearer {COZE_API_KEY}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "bot_id": COZE_BOT_ID,
        "user_id": user_id,
        "stream": False,
        "auto_save_history": True,
        "additional_messages": [
            {
                "role": "user",
                "content": user_message,
                "content_type": "text"
            }
        ]
    }
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(COZE_API_URL, headers=headers, json=payload)
            result = response.json()
            
            if response.status_code == 200 and result.get("code") == 0:
                # 解析扣子返回的消息
                messages = result.get("data", {}).get("messages", [])
                for msg in messages:
                    if msg.get("role") == "assistant" and msg.get("type") == "answer":
                        return {
                            "content": msg.get("content", ""),
                            "message_id": msg.get("id", "")
                        }
                return {"content": "抱歉，AI暂时无法回复", "message_id": ""}
            else:
                return {"content": f"API错误: {result.get('msg', '未知错误')}", "message_id": ""}
    except Exception as e:
        return {"content": f"网络错误: {str(e)}", "message_id": ""}

# ============== API路由 ==============
@app.get("/")
async def root():
    return {"status": "ok", "service": "AI客服后端", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """处理客户消息，返回AI回复"""
    # 调用扣子API
    coze_result = await call_coze_api(request.message, request.user_id, request.platform)
    
    return ChatResponse(
        code=0,
        msg="success",
        data={
            "reply": coze_result.get("content", ""),
            "message_id": coze_result.get("message_id", ""),
            "platform": request.platform,
            "timestamp": datetime.now().isoformat()
        }
    )

@app.post("/api/webhook/{platform}")
async def webhook(platform: str, request: Request):
    """接收各平台回调消息"""
    try:
        body = await request.json()
        
        # 统一消息格式
        message_data = {
            "platform": platform,
            "data": body,
            "received_at": datetime.now().isoformat()
        }
        
        # 存储消息到队列（后续处理）
        print(f"[{platform}] 收到消息: {json.dumps(body, ensure_ascii=False)[:200]}")
        
        return {"code": 0, "msg": "received"}
    except Exception as e:
        return {"code": 1, "msg": str(e)}

@app.get("/api/platforms")
async def get_platforms():
    """获取已配置的平台列表"""
    return {
        "code": 0,
        "data": {
            "platforms": [
                {"id": "dy_feige", "name": "抖音飞鸽", "status": "active"},
                {"id": "tb_qianiu", "name": "淘宝千牛", "status": "active"},
                {"id": "douyin_web", "name": "抖店网页版", "status": "active"},
            ]
        }
    }

@app.get("/api/stats")
async def get_stats():
    """获取统计数据"""
    return {
        "code": 0,
        "data": {
            "today_messages": 0,
            "ai_replies": 0,
            "human_handoffs": 0,
            "avg_response_time": "0s"
        }
    }

# ============== 启动 ==============
if __name__ == "__main__":
    import uvicorn
    print("🚀 AI客服后端服务启动中...")
    print(f"📡 服务地址: http://localhost:8000")
    print(f"🔗 扣子Bot ID: {COZE_BOT_ID}")
    uvicorn.run(app, host="0.0.0.0", port=8000)
