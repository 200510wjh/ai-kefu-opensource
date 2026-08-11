# 阶段十四：PDF 与 Word 文档导入导出报告

生成时间：2026-07-16 20:27:30

## 本阶段目标

补齐前面阶段明确留下的文档能力缺口，让经营报表和知识库从 Markdown/纯文本推进到客户常用的 PDF 与 Word DOCX。

## 已完成内容

- 报表导出支持三种格式：
  - `markdown`
  - `pdf`
  - `docx`
- v1 报表导出接口支持格式参数：
  - `GET /api/v1/reports/{report_id}/export?format=markdown`
  - `GET /api/v1/reports/{report_id}/export?format=pdf`
  - `GET /api/v1/reports/{report_id}/export?format=docx`
- 知识库上传支持：
  - txt
  - md
  - csv
  - json
  - pdf
  - docx
- v1 知识库上传接口：
  - `POST /api/v1/knowledge/upload`
- 前端“经营分析”报表卡片新增 Markdown、PDF、Word 导出按钮。
- 前端“知识库”上传说明和文件选择器已支持 PDF/DOCX。

## 技术实现

- PDF 生成：使用 `reportlab`，支持中文报表文本。
- PDF 解析：使用 `pypdf` 抽取文本并导入知识库。
- Word 导出：使用标准库生成 DOCX OOXML 包，减少运行时依赖。
- Word 解析：使用标准库读取 `word/document.xml` 抽取段落文本。

## 安全与边界

- 上传文档大小限制为 5MB。
- 不支持加密 PDF。
- 旧版 `.doc` 需另存为 `.docx` 后上传。
- 文档导入只抽取文本，不自动发送消息、不自动发布内容。

## 本地验证

- Python 编译通过。
- 前端构建通过。
- TestClient 冒烟通过：
  - 生成经营日报。
  - 导出 Markdown/PDF/DOCX。
  - 下载导出 artifact。
  - 重新上传导出的 DOCX 并导入知识库。
  - 上传 PDF 并导入知识库。
- PDF 结构校验通过：
  - 页数：1 页。
  - 文本可由 `pypdf` 抽取。
- DOCX 结构校验通过：
  - 包含 `word/document.xml` 和 `word/styles.xml`。
  - 正文文本可抽取。

## 渲染说明

当前 Codex 运行时的 Poppler 包装脚本存在原生目录缺失，无法用 `pdftoppm` 渲染 PNG 做视觉复核。本阶段已完成文件生成、下载和文本结构校验；线上部署后仍建议用真实浏览器或办公软件抽查 PDF/DOCX 的视觉版式。
