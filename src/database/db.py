"""数据库模块 - SQLite操作"""
import sqlite3
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class Database:
    """SQLite数据库操作类"""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_dir = Path(__file__).parent.parent.parent
            db_dir.mkdir(exist_ok=True)
            db_path = str(db_dir / "data.db")
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    def _get_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def init_tables(self):
        """初始化数据库表"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # 商家账号表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                username TEXT NOT NULL,
                cookies TEXT,
                headers TEXT,
                status TEXT DEFAULT 'offline',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 扣子配置表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS kouzhi_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_url TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                api_key TEXT,
                enabled INTEGER DEFAULT 1,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 消息记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER,
                platform TEXT NOT NULL,
                customer_id TEXT,
                message TEXT,
                reply TEXT,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_id) REFERENCES accounts(id)
            )
        """)

        conn.commit()
        logger.info("数据库表初始化完成")

    def add_account(self, platform: str, username: str, cookies: str = None, headers: str = None) -> int:
        """添加商家账号"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO accounts (platform, username, cookies, headers) VALUES (?, ?, ?, ?)",
            (platform, username, cookies, headers)
        )
        conn.commit()
        return cursor.lastrowid

    def get_accounts(self, platform: str = None) -> List[Dict[str, Any]]:
        """获取账号列表"""
        conn = self._get_connection()
        cursor = conn.cursor()
        if platform:
            cursor.execute("SELECT * FROM accounts WHERE platform = ?", (platform,))
        else:
            cursor.execute("SELECT * FROM accounts")
        return [dict(row) for row in cursor.fetchall()]

    def update_account_status(self, account_id: int, status: str):
        """更新账号状态"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE accounts SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, account_id)
        )
        conn.commit()

    def update_account_cookies(self, account_id: int, cookies: str, headers: str):
        """更新账号Cookies"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE accounts SET cookies = ?, headers = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (cookies, headers, account_id)
        )
        conn.commit()

    def delete_account(self, account_id: int):
        """删除账号"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        conn.commit()

    def save_kouzhi_config(self, api_url: str, agent_id: str, api_key: str = None):
        """保存扣子配置"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM kouzhi_config")
        cursor.execute(
            "INSERT INTO kouzhi_config (api_url, agent_id, api_key) VALUES (?, ?, ?)",
            (api_url, agent_id, api_key)
        )
        conn.commit()

    def get_kouzhi_config(self) -> Optional[Dict[str, Any]]:
        """获取扣子配置"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM kouzhi_config LIMIT 1")
        row = cursor.fetchone()
        return dict(row) if row else None

    def save_message(self, account_id: int, platform: str, customer_id: str,
                     message: str, reply: str = None, status: str = "pending") -> int:
        """保存消息记录"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO messages (account_id, platform, customer_id, message, reply, status) VALUES (?, ?, ?, ?, ?, ?)",
            (account_id, platform, customer_id, message, reply, status)
        )
        conn.commit()
        return cursor.lastrowid

    def get_recent_messages(self, account_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """获取最近消息"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM messages WHERE account_id = ? ORDER BY created_at DESC LIMIT ?",
            (account_id, limit)
        )
        return [dict(row) for row in cursor.fetchall()]

    def close(self):
        """关闭数据库连接"""
        if self._conn:
            self._conn.close()
            self._conn = None