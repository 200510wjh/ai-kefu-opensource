# AI客服开源系统 (AI-Kefu-OSS)

> 高科技感多平台AI客服系统，支持抖音飞鸽、淘宝千牛、抖店网页版，对接扣子(Coze)AI实现智能自动回复。

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Node](https://img.shields.io/badge/node-18%2B-green.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-green.svg)

## 🎨 界面预览

采用赛博朋克/高科技风格设计：
- 深蓝黑底色 + 霓虹青/紫色光效
- 玻璃拟态面板
- 脉冲式状态指示
- 毛玻璃导航栏

## ✨ 核心功能

| 功能 | 说明 |
|------|------|
| 多平台接入 | 抖音飞鸽、淘宝千牛、抖店、快手、拼多多 |
| AI智能回复 | 对接扣子(Coze) API，自动生成回复 |
| 知识库 | 商品信息、FAQ智能检索 |
| 订单识别 | 自动识别订单编号 |
| 转接人工 | AI无法回答时转人工处理 |
| 数据统计 | 消息量、回复率、响应时间 |

## 🛠 技术栈

- **桌面应用**: Electron 28
- **后端服务**: Python FastAPI
- **AI对接**: 扣子(Coze) Open API
- **数据库**: SQLite
- **部署**: Docker

## 📦 安装

### 环境要求
- Node.js 18+
- Python 3.10+
- Docker (可选)

### 1. 克隆项目
```bash
git clone <repository-url>
cd ai-kefu-opensource
```

### 2. 安装前端依赖
```bash
npm install
```

### 3. 安装后端依赖
```bash
cd src/backend
pip install fastapi uvicorn httpx pydantic
```

### 4. 配置

创建 `src/backend/config.py`:
```python
COZE_API_KEY = "your-coze-api-key"
COZE_BOT_ID = "your-bot-id"
```

### 5. 启动

```bash
# 启动后端 (新窗口)
cd src/backend
python main.py

# 启动前端 (新窗口)
npm start
```

### 6. Docker部署
```bash
docker-compose up -d
```

## 🔧 配置说明

### 扣子(Coze)配置
1. 登录 [Coze平台](https://coze.cn)
2. 创建Bot，获取 Bot ID 和 API Key
3. 在后端配置中填入

### 抖音飞鸽配置
1. 打开抖音飞鸽商家版
2. 开放平台 → 消息推送配置
3. 填写回调地址: `http://your-domain/api/webhook/dy_feige`

### 淘宝千牛配置
1. 打开千牛工作台
2. 开放平台 → 消息推送配置  
3. 填写回调地址: `http://your-domain/api/webhook/tb_qianiu`

## 📁 项目结构

```
ai-kefu-opensource/
├── SPEC.md              # 项目规格说明
├── README.md            # 本文件
├── package.json         # 前端依赖
├── docker-compose.yml  # Docker部署
├── src/
│   ├── main.js         # Electron主进程
│   ├── preload.js      # 预加载脚本
│   ├── backend/
│   │   ├── main.py     # FastAPI后端
│   │   └── config.py   # 配置文件
│   ├── renderer/
│   │   ├── index.html   # 主界面
│   │   └── styles.css   # 样式文件
│   └── extensions/     # 浏览器插件
└── knowledge-base/     # 知识库文件
```

## 🚀 快速开始

1. 修改扣子API配置
2. 启动后端服务
3. 启动桌面客户端
4. 连接平台，开始使用

## 📝 API接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 服务健康检查 |
| `/api/chat` | POST | 发送消息获取AI回复 |
| `/api/webhook/{platform}` | POST | 接收平台回调 |
| `/api/platforms` | GET | 获取平台列表 |
| `/api/stats` | GET | 获取统计数据 |

## 🔒 安全注意

- API Key请勿提交到代码仓库
- 生产环境请使用HTTPS
- 建议使用环境变量存储敏感信息

## 📄 开源协议

MIT License

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📞 联系

如有问题，请提交Issue或联系开发者。
