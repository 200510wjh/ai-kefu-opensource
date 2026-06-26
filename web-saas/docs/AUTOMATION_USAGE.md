# 自动化脚本使用说明

更新时间：2026-06-24

## 当前已有脚本

### 1. 系统烟测

用途：检查线上 SaaS 是否正常。

命令：

```powershell
python scripts\smoke_test.py https://wjhai.cn/merchant-admin
```

会检查：

- 后端健康接口。
- 系统自检。
- AI 脚本生成。
- HyperFrames 出片计划。
- 脚本客服闭环。
- 图片生成接口，至少返回 prompt。
- 私信候选回复。
- 渲染任务队列。

成功时会输出类似：

```json
{
  "health": "ok",
  "diagnostics": "warn",
  "scripts": {"count": 5, "scenes": 3},
  "script_customer_service": {"opening": 2, "qualification": 3, "objections": 3, "closing": 2},
  "image_generation": {"mode": "prompt", "has_prompt": true, "has_image": false},
  "reply_candidates": 3,
  "render": {"status": "done", "progress": 100, "artifact": true}
}
```

说明：

- `diagnostics: warn` 不等于故障，当前 warn 的原因通常是 GitHub remote、Fireflies、真实 MP4 渲染 worker 或图片模型权限还没完全接上。
- `image_generation.mode: prompt` 表示图片接口没真出图，但 prompt 已生成，系统可继续用。

### 2. 密钥扫描

用途：公开仓库或部署前检查有没有把 API Key、Token、密码写进代码。

命令：

```powershell
python scripts\secret_scan.py
```

成功时：

```text
No obvious secrets found.
```

如果发现疑似密钥，先不要推 GitHub，处理后再扫一次。

## 线上部署后推荐顺序

每次改完代码后按这个顺序：

```powershell
$env:VITE_BASE_PATH='/merchant-admin/'; npm run build; Remove-Item Env:VITE_BASE_PATH
python -m compileall backend
python scripts\secret_scan.py
python scripts\smoke_test.py https://wjhai.cn/merchant-admin
```

## Chrome 插件怎么用

适合做：

- 查看当前登录态页面，比如抖音收藏页、抖店后台、API2D 后台。
- 读取页面可见内容并总结。
- 测试你的 SaaS 页面按钮、导航和展示是否正常。
- 把聊天记录从网页中读出来，生成候选回复。

不建议直接做：

- 自动发送私信。
- 自动发布商品。
- 自动改价。
- 自动退款。
- 自动提交带敏感信息的表单。

这些动作必须停在“草稿/候选/待确认”状态，最后由人工点发送或发布。

推荐流程：

```text
打开目标网页
-> 让 Codex 用 Chrome 读取页面
-> 生成脚本、客服话术、商品草稿或操作清单
-> 人工确认
-> 再执行发送/发布
```

## 电脑插件怎么用

适合做：

- 操作本地 Windows 软件。
- 查看桌面 App。
- 打开剪映、浏览器、文件管理器等本地软件。
- 做非敏感、可撤销的重复操作。

不建议直接做：

- 输入密码。
- 提交付款。
- 删除大量文件。
- 自动群发消息。
- 不经确认发布内容。

## 后续要做的自动化脚本

### 1. 抖音收藏分析脚本

输入：

- 已打开的抖音收藏页。

输出：

- 收藏视频标题列表。
- 高频主题。
- 可复制选题。
- 产品功能建议。

状态：当前通过 Chrome 手动读过首屏，后续可做成专用脚本。

### 2. 商家需求转脚本客服脚本

输入：

- 行业。
- 商品/门店名。
- 卖点。
- 平台。
- 目标人群。
- 转化动作。

输出：

- 5 个短视频脚本。
- 分镜。
- 客服开场话术。
- 异议处理。
- 成交收口。

状态：当前已通过 API 实现，可通过 `smoke_test.py` 验证。

### 3. 商品图生成脚本

输入：

- 商品信息。
- 图片类型：主图、场景图、详情图。

输出：

- 图片 prompt。
- 如果图片模型可用，则输出图片 URL。

状态：接口已接好；当前 API2D 图片模型权限不可用，所以走 prompt 兜底。

### 4. 平台草稿自动化脚本

输入：

- 商品档案。
- 主图/详情图。
- 文案。

输出：

- 抖店/淘宝商品草稿。

安全规则：

- 只创建草稿。
- 不自动发布。
- 不自动改价。
- 不自动退款。

状态：待做。

