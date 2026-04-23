"""扣子智能体接入插件 - 主程序入口"""
import sys
import logging
from pathlib import Path

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from ui.main_window import MainWindow
from database.db import Database

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """应用入口函数"""
    # 初始化数据库
    db = Database()
    db.init_tables()

    # 创建应用
    app = QApplication(sys.argv)
    app.setApplicationName("扣子智能体接入插件")
    app.setApplicationVersion("1.0.0")

    # 设置应用样式
    app.setStyle("Fusion")

    # 创建并显示主窗口
    window = MainWindow(db)
    window.show()

    logger.info("应用启动成功")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()