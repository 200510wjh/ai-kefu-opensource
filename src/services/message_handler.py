"""消息处理模块 - 消息中枢"""
import asyncio
import logging
from typing import Dict, Any, Optional
from services.kouzhi_service import KouzhiService

logger = logging.getLogger(__name__)


class MessageHandler:
    """消息处理中枢，协调各服务"""

    def __init__(self, kouzhi_service: Optional[KouzhiService] = None):
        self._kouzhi_service = kouzhi_service
        self._douyin_handler = None
        self._taobao_handler = None
        self._running = False
        self._message_queue: asyncio.Queue = asyncio.Queue()

    def set_kouzhi_service(self, service: KouzhiService):
        """设置扣子服务"""
        self._kouzhi_service = service

    async def handle_message(self, platform: str, account_id: int, customer_id: str, message: str) -> bool:
        """
        处理单条消息

        Args:
            platform: 平台类型 ('douyin' 或 'taobao')
            account_id: 账号ID
            customer_id: 客户ID
            message: 用户消息

        Returns:
            是否成功处理
        """
        if not self._kouzhi_service:
            logger.error("扣子服务未配置")
            return False

        try:
            # 调用扣子智能体生成回复
            result = await self._kouzhi_service.generate_reply(
                user_message=message,
                context={
                    "platform": platform,
                    "account_id": account_id,
                    "customer_id": customer_id
                }
            )

            if result.get("success"):
                reply = result.get("reply", "")
                logger.info(f"生成回复成功: {reply[:50]}...")
                return True
            else:
                logger.error(f"生成回复失败: {result.get('error')}")
                return False

        except Exception as e:
            logger.error(f"消息处理异常: {e}")
            return False

    async def start(self, douyin_service, taobao_service):
        """启动消息处理"""
        self._running = True
        self._douyin_handler = douyin_service
        self._taobao_handler = taobao_service

        # 启动消息队列处理
        asyncio.create_task(self._process_queue())

        logger.info("消息处理中枢已启动")

    async def stop(self):
        """停止消息处理"""
        self._running = False
        if self._douyin_handler:
            await self._douyin_handler.stop()
        if self._taobao_handler:
            await self._taobao_handler.stop()
        logger.info("消息处理中枢已停止")

    async def _process_queue(self):
        """处理消息队列"""
        while self._running:
            try:
                msg = await self._message_queue.get()
                await self.handle_message(
                    platform=msg['platform'],
                    account_id=msg['account_id'],
                    customer_id=msg['customer_id'],
                    message=msg['message']
                )
            except Exception as e:
                logger.error(f"队列处理异常: {e}")

    async def enqueue_message(self, platform: str, account_id: int, customer_id: str, message: str):
        """将消息加入队列"""
        await self._message_queue.put({
            'platform': platform,
            'account_id': account_id,
            'customer_id': customer_id,
            'message': message
        })