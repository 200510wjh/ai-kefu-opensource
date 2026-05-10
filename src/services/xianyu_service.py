"""闲鱼服务 - 闲鱼IM消息监听"""
import asyncio
import logging
import json
from typing import Optional, Dict, Any, Callable
from playwright.async_api import async_playwright, Browser, Page, BrowserContext

logger = logging.getLogger(__name__)


class XianyuService:
    """闲鱼消息监听服务"""

    IM_URL = "https://message.taobao.com"

    def __init__(self, account_id: int, cookies: str = None):
        self.account_id = account_id
        self._cookies = json.loads(cookies) if cookies else []
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._running = False
        self._last_messages: Dict[str, str] = {}

    async def login(self) -> Dict[str, Any]:
        """登录闲鱼/淘宝消息"""
        try:
            async with async_playwright() as p:
                self._browser = await p.chromium.launch(headless=True)
                self._context = await self._browser.new_context(
                    viewport={"width": 1280, "height": 720},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                )

                if self._cookies:
                    await self._context.add_cookies(self._cookies)

                self._page = await self._context.new_page()

                await self._page.goto(self.IM_URL, wait_until="networkidle", timeout=60000)

                logger.info("等待闲鱼/淘宝消息页面加载...")
                await self._page.wait_for_timeout(3000)

                self._cookies = await self._context.cookies()

                logger.info("闲鱼消息页面加载成功")
                return {
                    "success": True,
                    "cookies": json.dumps(self._cookies)
                }

        except Exception as e:
            logger.error(f"闲鱼页面加载失败: {e}")
            return {"success": False, "error": str(e)}

    async def start_message_listener(self, callback: Callable):
        """启动消息监听"""
        self._running = True
        while self._running:
            try:
                messages = await self._fetch_messages()
                for msg in messages:
                    await callback(msg)
                await asyncio.sleep(3)
            except Exception as e:
                logger.error(f"闲鱼消息监听异常: {e}")
                await asyncio.sleep(10)

    async def _fetch_messages(self) -> list:
        """获取消息列表"""
        try:
            await self._page.goto(self.IM_URL, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)

            messages = await self._page.evaluate("""
                () => {
                    const result = [];
                    const items = document.querySelectorAll('[class*="message-item"], [class*="chat-item"]');

                    items.forEach((item, index) => {
                        const contentEl = item.querySelector('[class*="content"], [class*="text"], p');
                        const userEl = item.querySelector('[class*="user"], [class*="name"], [class*="nick"]');

                        if (contentEl) {
                            result.push({
                                id: item.dataset.id || index.toString(),
                                content: contentEl.innerText.trim(),
                                user: userEl ? userEl.innerText.trim() : '买家',
                                timestamp: Date.now()
                            });
                        }
                    });

                    return result;
                }
            """)

            new_messages = []
            for msg in messages:
                msg_id = msg.get('id', '')
                content = msg.get('content', '')

                if content and self._last_messages.get(msg_id) != content:
                    new_messages.append(msg)
                    self._last_messages[msg_id] = content

            if len(self._last_messages) > 100:
                keys = list(self._last_messages.keys())[:-50]
                for k in keys:
                    del self._last_messages[k]

            return new_messages

        except Exception as e:
            logger.error(f"获取闲鱼消息失败: {e}")
            return []

    async def send_reply(self, conversation_id: str, reply: str) -> bool:
        """发送回复"""
        try:
            await self._page.fill('textarea[class*="input"]', reply)
            await asyncio.sleep(0.5)
            await self._page.click('button[class*="send"]')
            await asyncio.sleep(1)
            logger.info(f"闲鱼消息发送成功: {conversation_id}")
            return True
        except Exception as e:
            logger.error(f"闲鱼消息发送失败: {e}")
            return False

    async def logout(self):
        """退出登录"""
        self._running = False
        if self._page:
            await self._page.close()
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()

    def get_cookies(self) -> str:
        return json.dumps(self._cookies)

    def get_user_info(self) -> Dict[str, Any]:
        """获取用户信息"""
        try:
            if self._page:
                return self._page.evaluate("""
                    () => {
                        const nickEl = document.querySelector('[class*="nick"], [class*="user-name"]');
                        return {
                            nick: nickEl ? nickEl.innerText : '闲鱼用户',
                            url: window.location.href
                        };
                    }
                """)
        except:
            pass
        return {"nick": "闲鱼用户", "url": ""}
