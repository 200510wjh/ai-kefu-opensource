"""PyQt6 UI模块 - 主窗口"""
import asyncio
import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTableWidget, QTableWidgetItem, QTabWidget,
    QMessageBox, QSystemTrayIcon, QMenu, QStatusBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon, QAction

from services.douyin_service import DouyinService
from services.taobao_service import TaobaoService
from services.kouzhi_service import KouzhiService

logger = logging.getLogger(__name__)


class WorkerThread(QThread):
    """异步工作线程"""
    finished = pyqtSignal(bool, str)
    log_signal = pyqtSignal(str)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs

    def run(self):
        asyncio.run(self._execute())

    async def _execute(self):
        try:
            result = await self._func(*self._args, **self._kwargs)
            self.finished.emit(True, str(result))
        except Exception as e:
            self.finished.emit(False, str(e))


class MainWindow(QWidget):
    """主窗口"""

    def __init__(self, db):
        super().__init__()
        self.db = db
        self._services = {}
        self._running = False
        self.init_ui()
        self.init_tray()

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("扣子智能体接入插件")
        self.setMinimumSize(900, 600)

        layout = QVBoxLayout()

        # 标签页
        tabs = QTabWidget()

        # 账号管理页
        accounts_tab = QWidget()
        accounts_layout = QVBoxLayout(accounts_tab)

        # 工具栏
        toolbar = QHBoxLayout()
        self.btn_add_douyin = QPushButton("添加抖店账号")
        self.btn_add_taobao = QPushButton("添加淘宝账号")
        self.btn_delete = QPushButton("删除账号")
        self.btn_login = QPushButton("登录")
        self.btn_logout = QPushButton("退出登录")
        toolbar.addWidget(self.btn_add_douyin)
        toolbar.addWidget(self.btn_add_taobao)
        toolbar.addWidget(self.btn_delete)
        toolbar.addWidget(self.btn_login)
        toolbar.addWidget(self.btn_logout)
        toolbar.addStretch()
        accounts_layout.addLayout(toolbar)

        # 账号表格
        self.accounts_table = QTableWidget()
        self.accounts_table.setColumnCount(5)
        self.accounts_table.setHorizontalHeaderLabels(["ID", "平台", "用户名", "状态", "操作"])
        accounts_layout.addWidget(self.accounts_table)

        # 设置页
        settings_tab = QWidget()
        settings_layout = QVBoxLayout(settings_tab)

        # 扣子配置
        kouzhi_group = QWidget()
        kouzhi_layout = QVBoxLayout(kouzhi_group)

        api_url_label = QLabel("API地址:")
        self.api_url_input = QLabel()
        agent_id_label = QLabel("Agent ID:")
        self.agent_id_input = QLabel()

        kouzhi_layout.addWidget(api_url_label)
        kouzhi_layout.addWidget(self.api_url_input)
        kouzhi_layout.addWidget(agent_id_label)
        kouzhi_layout.addWidget(self.agent_id_input)

        btn_test = QPushButton("测试连接")
        btn_save = QPushButton("保存配置")
        kouzhi_layout.addWidget(btn_test)
        kouzhi_layout.addWidget(btn_save)

        settings_layout.addWidget(kouzhi_group)
        settings_layout.addStretch()

        tabs.addTab(accounts_tab, "账号管理")
        tabs.addTab(settings_tab, "扣子配置")

        layout.addWidget(tabs)

        # 状态栏
        self.status_bar = QStatusBar()
        self.status_label = QLabel("就绪")
        self.status_bar.addWidget(self.status_label)
        layout.addWidget(self.status_bar)

        # 按钮事件
        self.btn_add_douyin.clicked.connect(self.add_douyin_account)
        self.btn_add_taobao.clicked.connect(self.add_taobao_account)
        self.btn_delete.clicked.connect(self.delete_account)
        self.btn_login.clicked.connect(self.login_account)
        self.btn_logout.clicked.connect(self.logout_account)
        btn_test.clicked.connect(self.test_kouzhi_connection)
        btn_save.clicked.connect(self.save_kouzhi_config)

        self.setLayout(layout)
        self.load_accounts()

    def init_tray(self):
        """初始化系统托盘"""
        self.tray = QSystemTrayIcon(self)
        self.tray.setToolTip("扣子智能体接入插件")

        menu = QMenu()
        menu.addAction("显示", self.show)
        menu.addAction("启动", self.start_service)
        menu.addAction("停止", self.stop_service)
        menu.addAction("退出", self.quit_app)
        self.tray.setContextMenu(menu)
        self.tray.show()

    def load_accounts(self):
        """加载账号列表"""
        accounts = self.db.get_accounts()
        self.accounts_table.setRowCount(len(accounts))
        for i, acc in enumerate(accounts):
            self.accounts_table.setItem(i, 0, QTableWidgetItem(str(acc['id'])))
            self.accounts_table.setItem(i, 1, QTableWidgetItem(acc['platform']))
            self.accounts_table.setItem(i, 2, QTableWidgetItem(acc['username']))
            self.accounts_table.setItem(i, 3, QTableWidgetItem(acc['status']))
            self.accounts_table.setItem(i, 4, QTableWidgetItem("查看"))

    def add_douyin_account(self):
        """添加抖店账号"""
        self.status_label.setText("添加抖店账号...")
        QMessageBox.information(self, "提示", "功能开发中")

    def add_taobao_account(self):
        """添加淘宝账号"""
        self.status_label.setText("添加淘宝账号...")
        QMessageBox.information(self, "提示", "功能开发中")

    def delete_account(self):
        """删除账号"""
        selected = self.accounts_table.currentRow()
        if selected >= 0:
            account_id = int(self.accounts_table.item(selected, 0).text())
            self.db.delete_account(account_id)
            self.load_accounts()
            QMessageBox.information(self, "成功", "账号已删除")

    def login_account(self):
        """登录账号"""
        selected = self.accounts_table.currentRow()
        if selected >= 0:
            self.status_label.setText("登录中...")
            QMessageBox.information(self, "提示", "功能开发中")

    def logout_account(self):
        """退出登录"""
        selected = self.accounts_table.currentRow()
        if selected >= 0:
            account_id = int(self.accounts_table.item(selected, 0).text())
            self.db.update_account_status(account_id, "offline")
            self.load_accounts()

    def test_kouzhi_connection(self):
        """测试扣子连接"""
        config = self.db.get_kouzhi_config()
        if not config:
            QMessageBox.warning(self, "警告", "请先保存扣子配置")
            return
        self.status_label.setText("测试连接中...")
        QMessageBox.information(self, "提示", "功能开发中")

    def save_kouzhi_config(self):
        """保存扣子配置"""
        QMessageBox.information(self, "提示", "功能开发中")

    def start_service(self):
        """启动服务"""
        self._running = True
        self.status_label.setText("服务运行中")
        logger.info("服务已启动")

    def stop_service(self):
        """停止服务"""
        self._running = False
        self.status_label.setText("服务已停止")
        logger.info("服务已停止")

    def quit_app(self):
        """退出应用"""
        self.tray.hide()
        self.close()

    def closeEvent(self, event):
        """关闭事件"""
        event.ignore()
        self.hide()
        self.tray.showMessage("扣子智能体接入插件", "应用已最小化到托盘")