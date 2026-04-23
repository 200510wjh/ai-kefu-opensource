# 扣子智能体接入插件 - 抖店/淘宝自动回复工具

简体中文 | [English](README_en.md)

一款开源桌面应用程序，帮助商家将扣子(Cohere)智能体快速接入抖音小店和淘宝店铺客服系统，实现自动实时回复客户咨询。

## 功能特性

- 🤖 **扣子智能体接入** - 支持配置扣子API地址和机器ID
- 🛒 **抖店支持** - 登录抖音小店商家后台，自动处理客户咨询
- 🛍️ **淘宝支持** - 登录淘宝商家千牛工作台，自动回复消息
- ⚡ **实时自动回复** - 智能体自动生成回复，毫秒级响应
- 🔐 **安全存储** - 账号信息加密本地存储
- 💻 **桌面应用** - PyQt6现代化界面，系统托盘运行

## 系统要求

- Windows 10/11 (64-bit)
- Python 3.10+
- 网络连接（用于登录电商平台和调用扣子API）

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/yourusername/kouzhi-agent.git
cd kouzhi-agent
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 运行应用

```bash
cd src
python main.py
```

## 使用说明

### 添加商家账号

1. 点击"添加账号"按钮
2. 选择平台（抖店/淘宝）
3. 通过二维码或账号密码登录
4. 账号信息将安全保存在本地

### 配置扣子智能体

1. 进入"设置"页面
2. 填入扣子API地址和机器ID
3. 点击"测试连接"验证配置

### 启动自动回复

1. 确保已添加商家账号
2. 确保已配置扣子智能体
3. 点击"启动"按钮
4. 应用将在后台监听消息并自动回复

## 项目结构

```
kouzhi-agent/
├── src/
│   ├── main.py              # 程序入口
│   ├── ui/                  # PyQt6界面
│   │   ├── main_window.py   # 主窗口
│   │   ├── login_window.py  # 登录窗口
│   │   └── settings_dialog.py
│   ├── services/             # 核心服务
│   │   ├── douyin_service.py # 抖店服务
│   │   ├── taobao_service.py # 淘宝服务
│   │   ├── kouzhi_service.py # 扣子API
│   │   └── message_handler.py # 消息处理
│   ├── models/               # 数据模型
│   └── database/             # 数据库操作
├── requirements.txt
├── README.md
└── LICENSE
```

## 技术栈

- **GUI**: PyQt6
- **浏览器自动化**: Playwright
- **HTTP客户端**: httpx
- **数据存储**: SQLite
- **打包**: PyInstaller

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 贡献

欢迎提交 Issue 和 Pull Request！