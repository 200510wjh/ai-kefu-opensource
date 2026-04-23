"""扣子智能体API服务"""
import httpx
import logging
import json
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class KouzhiService:
    """扣子智能体API调用服务"""

    def __init__(self, api_url: str, agent_id: str, api_key: str = None):
        self.api_url = api_url.rstrip('/')
        self.agent_id = agent_id
        self.api_key = api_key
        self._client: Optional[httpx.AsyncClient] = None

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> 'KouzhiService':
        """从配置创建服务实例"""
        return cls(
            api_url=config['api_url'],
            agent_id=config['agent_id'],
            api_key=config.get('api_key')
        )

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def test_connection(self) -> Dict[str, Any]:
        """测试API连接"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.api_url}/agents/{self.agent_id}",
                    headers=self._get_headers()
                )
                if response.status_code == 200:
                    return {"success": True, "data": response.json()}
                else:
                    return {"success": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            logger.error(f"扣子API连接测试失败: {e}")
            return {"success": False, "error": str(e)}

    async def generate_reply(self, user_message: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        调用扣子智能体生成回复

        Args:
            user_message: 用户发送的消息
            context: 上下文信息（店铺信息、商品信息等）

        Returns:
            包含回复内容的字典
        """
        try:
            payload = {
                "agent_id": self.agent_id,
                "message": user_message,
                "context": context or {}
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.api_url}/chat",
                    headers=self._get_headers(),
                    json=payload
                )

                if response.status_code == 200:
                    result = response.json()
                    return {
                        "success": True,
                        "reply": result.get("reply", ""),
                        "confidence": result.get("confidence", 1.0)
                    }
                else:
                    logger.error(f"扣子API调用失败: HTTP {response.status_code}")
                    return {"success": False, "error": f"HTTP {response.status_code}"}

        except httpx.TimeoutException:
            logger.error("扣子API调用超时")
            return {"success": False, "error": "请求超时"}
        except Exception as e:
            logger.error(f"扣子API调用异常: {e}")
            return {"success": False, "error": str(e)}

    async def close(self):
        """关闭客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None