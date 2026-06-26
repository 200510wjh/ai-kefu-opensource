# AI ??????

## Web SaaS ??

????? `web-saas/` ???????? AI ?? SaaS?

- ??????????
- ????? FAQ ???
- ????/SOP ??
- ????????????????
- ????????
- ????????????

?????

```bash
cd web-saas
npm install
pip install -r requirements.txt
npm run api
npm run dev
```

????????`web-saas/docs/OPEN_SOURCE_ADAPTERS.md`?

---

# AI客服 - 多平台智能客服系统

> 一款面向电商商家的**多平台AI客服解决方案**，支持抖店、淘宝千牛、快手、拼多多，自动回复客户消息，提升客服效率。

## 功能特性

| 功能 | 说明 |
|------|------|
| 多平台接入 | 抖店、淘宝千牛、快手、拼多多 |
| AI智能回复 | 对接扣子(Coze) API，自动生成回复 |
| 店铺管理 | 添加/删除/启用/禁用多店铺 |
| 知识库 | 商品信息、FAQ智能检索 |
| 数据统计 | 消息量、回复率、响应时间 |
| 实时监控 | 店铺连接状态实时显示 |

## 技术栈

- **桌面应用**: PyQt6
- **浏览器自动化**: Playwright
- **AI对接**: 扣子(Coze) Open API
- **数据库**: SQLite

## 快速开始

```bash
pip install -r requirements.txt
playwright install chromium
python src/main.py
```

## 项目结构

```
kouzhi-agent/
├── src/
│   ├── main.py              # 程序入口
│   ├── ui/                  # PyQt6界面
│   ├── services/            # 核心服务
│   │   ├── douyin_service.py # 抖店服务
│   │   ├── taobao_service.py # 淘宝服务
│   │   ├── kouzhi_service.py # 扣子API
│   │   └── message_handler.py # 消息处理
│   ├── models/              # 数据模型
│   └── database/            # 数据库操作
├── requirements.txt
└── README.md
```

## 许可证

MIT License