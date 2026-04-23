# AI客服 - 多平台智能客服系统

> 一款面向电商商家的**多平台AI客服解决方案**，支持抖店、淘宝千牛、快手、拼多多，自动回复客户消息，提升客服效率。

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Version](https://img.shields.io/badge/version-1.0.0-green.svg)
![Price](https://img.shields.io/badge/price-¥49%2F%E6%9C%88-red.svg)

---

## 🎨 界面预览

采用**字节跳动级别高级设计**：
- ✨ 动态粒子/光球背景
- ✨ 玻璃拟态卡片效果
- ✨ 渐变流光动画
- ✨ 悬浮发光交互
- ✨ 弹性点击反馈
- ✨ 脉冲状态指示

---

## ✨ 核心功能

| 功能 | 说明 |
|------|------|
| 多平台接入 | 抖店、淘宝千牛、快手、拼多多 |
| AI智能回复 | 对接扣子(Coze) API，自动生成回复 |
| 店铺管理 | 添加/删除/启用/禁用多店铺 |
| 知识库 | 商品信息、FAQ智能检索 |
| 数据统计 | 消息量、回复率、响应时间 |
| 实时监控 | 店铺连接状态实时显示 |

---

## 💰 价格

**¥49/月** - 包含全部功能

---

## 🛠 技术栈

- **桌面应用**: Electron 28
- **后端服务**: Python FastAPI
- **AI对接**: 扣子(Coze) Open API
- **前端**: 原生 HTML/CSS/JS（高性能）
- **数据库**: JSON文件存储

---

## 🚀 快速开始

### 1. 安装依赖

```bash
# Windows
.\install.bat

# Linux/Mac
chmod +x install.sh
./install.sh
```

### 2. 启动后端

```bash
cd src/backend
pip install -r requirements.txt
python main.py
```

### 3. 启动前端

```bash
npm start
```

---

## 📁 项目结构

```
ai-kefu-opensource/
├── data/                  # 数据存储
│   └── database.json     # 店铺和配置数据
├── src/
│   ├── main.js          # Electron主进程
│   ├── preload.js       # IPC预加载
│   ├── backend/
│   │   ├── main.py      # FastAPI后端
│   │   └── requirements.txt
│   ├── renderer/
│   │   └── index.html   # 高科技风格界面
│   └── extensions/      # 浏览器插件
│       ├── dy.js        # 抖店
│       ├── qianiu.js    # 淘宝千牛
│       ├── ks.js        # 快手
│       └── pdd.js       # 拼多多
├── knowledge-base/      # 知识库
├── nginx/               # Nginx配置
├── package.json
├── docker-compose.yml
└── README.md
```

---

## 🔌 浏览器插件使用

1. 打开 `chrome://extensions/`
2. 开启**开发者模式**
3. 点击**加载已解压的扩展程序**
4. 选择 `src/extensions` 文件夹
5. 打开对应平台商家后台即可

---

## ⚙️ 配置说明

### 扣子(Coze)配置

1. 登录 [Coze平台](https://coze.cn)
2. 创建Bot，获取 Bot ID 和 API Key
3. 在系统「AI配置」页面填入

### 平台接入

| 平台 | 状态 | 插件 |
|------|------|------|
| 抖店 | ✅ 已支持 | dy.js |
| 淘宝千牛 | ✅ 已支持 | qianiu.js |
| 快手 | ✅ 已支持 | ks.js |
| 拼多多 | ✅ 已支持 | pdd.js |

---

## 📊 API接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `GET /api/stores` | 获取店铺列表 |
| `POST /api/stores` | 添加店铺 |
| `DELETE /api/stores/{id}` | 删除店铺 |
| `PUT /api/stores/{id}/toggle` | 启用/禁用店铺 |
| `GET /api/config` | 获取AI配置 |
| `PUT /api/config` | 更新AI配置 |
| `POST /api/chat` | 发送消息获取AI回复 |
| `GET /api/stats` | 获取统计数据 |

---

## 💡 开发计划

- [x] 店铺管理系统
- [x] AI配置面板
- [x] 四大平台插件
- [x] 数据统计
- [ ] 知识库管理界面
- [ ] 订单自动识别
- [ ] 转人工功能
- [ ] 消息历史查看

---

## 📄 开源协议

MIT License

---

**© 2026 AI客服 - 多平台智能客服系统**
