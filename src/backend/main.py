"""
AI客服后端服务 - FastAPI
对接扣子(Coze) API实现智能客服

版本: 1.0.0
更新: 2026-04-23
"""

import asyncio
import json
import logging
import uuid
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from collections import defaultdict
from fastapi import FastAPI, HTTPException, Header, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager
import httpx

# ============== 数据文件路径 ==============
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
DATABASE_FILE = os.path.join(DATA_DIR, 'database.json')
os.makedirs(DATA_DIR, exist_ok=True)

# ============== 配置文件 ==============
def load_database():
    """加载数据库"""
    if os.path.exists(DATABASE_FILE):
        with open(DATABASE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"stores": [], "config": {}, "stats": {"total_messages": 0, "ai_replies": 0, "human_handoffs": 0}}

def save_database(data):
    """保存数据库"""
    with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

db_data = load_database()

# ============== 配置 ==============
COZE_API_URL = "https://api.coze.cn/v1/chat"
COZE_BOT_ID = "7631125644738379811"
COZE_API_KEY = "pat_KaeGWcFwKM6WsXOLyiOypKvqn4gXwjPGyf6zNISlqTwAMQaS6z0gBkx24C5tbHun"

# ============== 日志配置 ==============
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ============== 内存存储 ==============
class MessageStore:
    """简单的内存消息存储"""
    def __init__(self):
        self.messages = defaultdict(list)
        self.stats = {
            "total_messages": 0,
            "ai_replies": 0,
            "human_handoffs": 0,
            "platform_stats": defaultdict(lambda: {"messages": 0, "replies": 0})
        }
    
    def add_message(self, platform: str, message: Dict):
        self.messages[platform].append({
            **message,
            "timestamp": datetime.now().isoformat()
        })
        self.stats["total_messages"] += 1
        self.stats["platform_stats"][platform]["messages"] += 1
    
    def add_reply(self, platform: str):
        self.stats["ai_replies"] += 1
        self.stats["platform_stats"][platform]["replies"] += 1
    
    def get_stats(self):
        return {
            **self.stats,
            "platform_stats": dict(self.stats["platform_stats"])
        }

message_store = MessageStore()

# ============== 生命周期管理 ==============
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 AI客服后端服务启动")
    logger.info(f"📡 扣子Bot ID: {COZE_BOT_ID}")
    yield
    logger.info("👋 AI客服后端服务关闭")

# ============== 创建应用 ==============
app = FastAPI(
    title="AI客服后端",
    version="1.0.0",
    description="多平台AI客服系统后端服务",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============== 店铺管理数据模型 ==============
class Store(BaseModel):
    id: str
    name: str
    platform: str  # douyin, qianiu, kuaishou, pinduoduo
    status: str = "active"  # active, inactive, error
    config: Dict[str, Any] = {}
    created_at: str
    updated_at: str

class StoreCreate(BaseModel):
    name: str
    platform: str
    config: Dict[str, Any] = {}

class ConfigUpdate(BaseModel):
    coze_api_key: Optional[str] = None
    coze_bot_id: Optional[str] = None

# ============== 店铺管理API ==============

@app.get("/api/stores")
async def get_stores():
    """获取所有店铺"""
    data = load_database()
    return {"code": 0, "data": {"stores": data.get("stores", [])}}

@app.post("/api/stores")
async def create_store(store: StoreCreate):
    """添加新店铺"""
    data = load_database()
    
    # 检查平台是否已存在
    for s in data.get("stores", []):
        if s.get("platform") == store.platform:
            return {"code": 1, "msg": f"{store.platform} 已存在，请先删除再添加"}
    
    new_store = {
        "id": str(uuid.uuid4())[:8],
        "name": store.name,
        "platform": store.platform,
        "status": "active",
        "config": store.config,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    
    data.setdefault("stores", []).append(new_store)
    save_database(data)
    
    logger.info(f"[店铺] 添加新店铺: {new_store['name']} ({new_store['platform']})")
    return {"code": 0, "msg": "success", "data": {"store": new_store}}

@app.delete("/api/stores/{store_id}")
async def delete_store(store_id: str):
    """删除店铺"""
    data = load_database()
    stores = data.get("stores", [])
    
    for i, s in enumerate(stores):
        if s.get("id") == store_id:
            deleted = stores.pop(i)
            save_database(data)
            logger.info(f"[店铺] 删除店铺: {deleted['name']}")
            return {"code": 0, "msg": "success"}
    
    return {"code": 1, "msg": "店铺不存在"}

@app.put("/api/stores/{store_id}/toggle")
async def toggle_store(store_id: str):
    """启用/禁用店铺"""
    data = load_database()
    stores = data.get("stores", [])
    
    for s in stores:
        if s.get("id") == store_id:
            s["status"] = "inactive" if s.get("status") == "active" else "active"
            s["updated_at"] = datetime.now().isoformat()
            save_database(data)
            logger.info(f"[店铺] 切换店铺状态: {s['name']} -> {s['status']}")
            return {"code": 0, "msg": "success", "data": {"store": s}}
    
    return {"code": 1, "msg": "店铺不存在"}

@app.get("/api/config")
async def get_config():
    """获取AI配置"""
    data = load_database()
    config = data.get("config", {})
    # 不要返回完整的API Key，只返回后4位
    if config.get("coze_api_key"):
        config["coze_api_key_masked"] = "****" + config["coze_api_key"][-4:]
    return {"code": 0, "data": {"config": config}}

@app.put("/api/config")
async def update_config(config: ConfigUpdate):
    """更新AI配置"""
    data = load_database()
    
    if config.coze_api_key:
        data.setdefault("config", {})["coze_api_key"] = config.coze_api_key
    if config.coze_bot_id:
        data.setdefault("config", {})["coze_bot_id"] = config.coze_bot_id
    
    save_database(data)
    logger.info("[配置] AI配置已更新")
    return {"code": 0, "msg": "success"}

@app.post("/api/stores/test-connection")
async def test_connection(store: StoreCreate):
    """测试店铺连接"""
    # 模拟连接测试
    logger.info(f"[店铺] 测试连接: {store.platform}")
    return {"code": 0, "msg": "连接成功", "data": {"status": "ok"}}

# ============== 消息处理数据模型 ==============
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

class WebhookRequest(BaseModel):
    platform: str
    data: Dict[str, Any]

# ============== 扣子API对接 ==============
async def call_coze_api(user_message: str, user_id: str, platform: str) -> Dict[str, Any]:
    """调用扣子API获取AI回复"""
    headers = {
        "Authorization": f"Bearer {COZE_API_KEY}",
        "Content-Type": "application/json",
    }
    
    # 构建发送给扣子的消息，包含平台上下文
    full_message = f"[{platform}] {user_message}"
    
    payload = {
        "bot_id": COZE_BOT_ID,
        "user_id": f"{platform}_{user_id}",
        "stream": False,
        "auto_save_history": True,
        "additional_messages": [
            {
                "role": "user",
                "content": full_message,
                "content_type": "text"
            }
        ]
    }
    
    logger.info(f"[{platform}] 调用扣子API，用户: {user_id}")
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(COZE_API_URL, headers=headers, json=payload)
            result = response.json()
            
            if response.status_code == 200 and result.get("code") == 0:
                messages = result.get("data", {}).get("messages", [])
                for msg in messages:
                    if msg.get("role") == "assistant" and msg.get("type") == "answer":
                        content = msg.get("content", "").strip()
                        logger.info(f"[{platform}] AI回复: {content[:50]}...")
                        message_store.add_reply(platform)
                        return {"content": content, "message_id": msg.get("id", "")}
                
                logger.warning(f"[{platform}] 扣子返回无有效消息")
                return {"content": "抱歉，AI暂时无法回复，请稍后再试", "message_id": ""}
            else:
                error_msg = result.get('msg', '未知错误')
                logger.error(f"[{platform}] 扣子API错误: {error_msg}")
                return {"content": f"AI服务暂时繁忙，请稍后再试", "message_id": ""}
                
    except httpx.TimeoutException:
        logger.error(f"[{platform}] 扣子API超时")
        return {"content": "AI响应超时，请稍后再试", "message_id": ""}
    except Exception as e:
        logger.error(f"[{platform}] 调用扣子API异常: {str(e)}")
        return {"content": "网络错误，请检查连接后重试", "message_id": ""}

# ============== API路由 ==============
@app.get("/")
async def root():
    """服务首页"""
    return {
        "service": "AI客服后端",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health():
    """健康检查"""
    return {
        "status": "healthy",
        "uptime": "running",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """处理客户消息，返回AI回复"""
    logger.info(f"[{request.platform}] 收到消息 from {request.user_id}: {request.message[:30]}...")
    
    # 存储消息
    message_store.add_message(request.platform, {
        "user_id": request.user_id,
        "content": request.message,
        "order_no": request.order_no
    })
    
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
async def webhook(platform: str, request: Request, background_tasks: BackgroundTasks):
    """接收各平台回调消息"""
    try:
        body = await request.json()
        
        logger.info(f"[{platform}] 收到回调: {json.dumps(body, ensure_ascii=False)[:100]}...")
        
        # 异步处理消息
        background_tasks.add_task(process_webhook_message, platform, body)
        
        return {"code": 0, "msg": "received"}
    except Exception as e:
        logger.error(f"[{platform}] 处理回调失败: {str(e)}")
        return {"code": 1, "msg": str(e)}

async def process_webhook_message(platform: str, body: Dict):
    """后台处理 webhook 消息"""
    try:
        # 提取消息内容
        message = extract_message_from_webhook(platform, body)
        if not message:
            logger.warning(f"[{platform}] 无法从回调中提取消息")
            return
        
        # 发送到扣子获取回复
        coze_result = await call_coze_api(
            message["content"],
            message.get("user_id", "unknown"),
            platform
        )
        
        if coze_result.get("content"):
            logger.info(f"[{platform}] 自动回复: {coze_result['content'][:30]}...")
            # 这里可以添加推送到平台的逻辑
            
    except Exception as e:
        logger.error(f"[{platform}] 处理消息异常: {str(e)}")

def extract_message_from_webhook(platform: str, body: Dict) -> Optional[Dict]:
    """从各平台webhook数据中提取消息"""
    try:
        if platform == "dy_feige":
            # 抖音飞鸽格式
            return {
                "content": body.get("content", ""),
                "user_id": body.get("open_id", body.get("user_id", "")),
                "order_no": body.get("order_no")
            }
        elif platform == "tb_qianiu":
            # 淘宝千牛格式
            return {
                "content": body.get("content", body.get("text", "")),
                "user_id": body.get("buyer_nick", body.get("user_id", "")),
                "order_no": body.get("order_id")
            }
        elif platform == "douyin":
            # 抖店网页格式
            return {
                "content": body.get("message", {}).get("content", ""),
                "user_id": body.get("user", {}).get("open_id", ""),
                "order_no": body.get("order_no")
            }
        else:
            # 通用格式
            return {
                "content": body.get("content", body.get("message", "")),
                "user_id": body.get("user_id", "unknown")
            }
    except Exception as e:
        logger.error(f"提取消息失败: {str(e)}")
        return None

@app.get("/api/platforms")
async def get_platforms():
    """获取已配置的平台列表"""
    return {
        "code": 0,
        "data": {
            "platforms": [
                {"id": "dy_feige", "name": "抖音飞鸽", "status": "active", "icon": "🐦"},
                {"id": "tb_qianiu", "name": "淘宝千牛", "status": "active", "icon": "🐱"},
                {"id": "douyin_web", "name": "抖店网页", "status": "active", "icon": "🏪"},
            ]
        }
    }

@app.get("/api/stats")
async def get_stats():
    """获取统计数据"""
    stats = message_store.get_stats()
    total = stats["total_messages"]
    replies = stats["ai_replies"]
    
    return {
        "code": 0,
        "data": {
            **stats,
            "reply_rate": f"{(replies/total*100):.1f}%" if total > 0 else "0%"
        }
    }

@app.get("/api/messages/{platform}")
async def get_messages(platform: str, limit: int = 50):
    """获取平台消息历史"""
    messages = message_store.messages.get(platform, [])[-limit:]
    return {
        "code": 0,
        "data": {
            "platform": platform,
            "count": len(messages),
            "messages": messages
        }
    }

# ============== 启动 ==============
if __name__ == "__main__":
    import uvicorn
    print("🚀 AI客服后端服务启动中...")
    print(f"📡 服务地址: http://localhost:8000")
    print(f"🔗 扣子Bot ID: {COZE_BOT_ID}")
    uvicorn.run(app, host="0.0.0.0", port=8000)
