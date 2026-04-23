"""抖店服务 - 抖音小店商家后台自动化"""
import asyncio
import logging
import json
from typing import Optional, Dict, Any, Callable
from playwright.async_api import async_playwright, Browser, Page, BrowserContext

logger = logging.getLogger(__name__)


class DouyinService:
    """抖店商家后台自动化服务"""

    LOGIN_URL = "https://seller.douyin.com/login"

    def __init__(self, account_id: int, cookies: str = None, headers: str = None):
        self.account_id = account_id
        self._cookies = json.loads(cookies) if cookies else []
        self._headers = json.loads(headers) if headers else {}
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._running = False

    async def login(self) -> Dict[str, Any]:
        """登录抖店商家后台"""
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

                # 访问登录页面
                await self._page.goto(self.LOGIN_URL, wait_until="networkidle", timeout=60000)

                # 等待用户扫码或输入密码
                logger.info("等待抖店登录...")
                await self._page.wait_for_url("**/seller**", timeout=120000)

                # 获取登录后的cookies
                self._cookies = await self._context.cookies()
                self._headers = {
                    "User-Agent": self._page.evaluate("() => navigator.userAgent"),
                    "Referer": "https://seller.douyin.com/"
                }

                logger.info("抖店登录成功")
                return {
                    "success": True,
                    "cookies": json.dumps(self._cookies),
                    "headers": json.dumps(self._headers)
                }

        except Exception as e:
            logger.error(f"抖店登录失败: {e}")
            return {"success": False, "error": str(e)}

    async def start_message_listener(self, callback: Callable):
        """启动消息监听"""
        self._running = True
        while self._running:
            try:
                # 获取消息列表
                messages = await self._fetch_messages()
                for msg in messages:
                    await callback(msg)
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"抖店消息监听异常: {e}")
                await asyncio.sleep(10)

    async def _fetch_messages(self) -> list:
        """获取消息列表"""
        try:
            # 访问消息页面
            await self._page.goto("https://seller.douyin.com/im到手消息", wait_until="networkidle")
            await asyncio.sleep(2)

            # 提取消息数据
            messages = await self._page.evaluate("""
                () => {
                    const items = document.querySelectorAll('.message-item');
                    return Array.from(items).map(item => ({
                        customer_id: item.dataset.customerId,
                        message: item.querySelector('.message-text')?.innerText,
                        timestamp: item.dataset.timestamp
                    }));
                }
            """)
            return messages

        except Exception as e:
            logger.error(f"获取抖店消息失败: {e}")
            return []

    async def send_reply(self, customer_id: str, reply: str) -> bool:
        """发送回复"""
        try:
            await self._page.fill(f'#reply-{customer_id}', reply)
            await self._page.click(f'#send-{customer_id}')
            await asyncio.sleep(1)
            logger.info(f"抖店消息发送成功: {customer_id}")
            return True
        except Exception as e:
            logger.error(f"抖店消息发送失败: {e}")
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

    def get_headers(self) -> str:
        return json.dumps(self._headers)