# 阶段七十二：开源 Connector 验收脚本报告

## 背景

当前生产真实平台验收仍缺 `official_auth`、`read_message`、`read_lead`、`customer_trial`。如果没有客户平台账号、OAuth 应用、只读 API 权限或真实样本，就不能把这些场景登记为生产 pass evidence。

阶段七十二补齐开源场景下的替代路径：开源演示可跑通，真实平台权限到位后可一键探测并生成脱敏报告。

## 已完成

- 新增 `scripts/open_source_connector_demo.py`
  - 离线生成开源 mock connector 验收产物。
  - 覆盖 `official_auth`、`read_message`、`read_lead`、`customer_trial` 的演示形态。
  - 明确标记为 `mock_open_source`，不当作生产真实证据。
- 新增 `scripts/real_connector_probe.py`
  - 读取 `REAL_CONNECTOR_*` 环境变量。
  - 对真实消息/线索只读 API 做探测。
  - 自动脱敏敏感字段。
  - 可选 `--ingest` 写入 SaaS connector read endpoint。
- 新增 `docs/OPEN_SOURCE_CONNECTOR_ACCEPTANCE.md`。
- 更新 `.env.example`，补充真实 connector probe 所需变量。
- 更新 `package.json`：
  - `npm run acceptance:open-source-demo`
  - `npm run acceptance:real-connector`
- 更新 `README.md`，加入开源演示和真实接入验证入口。

## 验证

- `python -m py_compile scripts/open_source_connector_demo.py scripts/real_connector_probe.py`：通过
- `npm run acceptance:open-source-demo`：通过，生成 demo artifact
- `npm run acceptance:real-connector`：通过，在无真实权限时返回 `setup_required`
- `python -m py_compile backend/customer_service_saas.py backend/api_v1.py backend/main.py`：通过
- `npm run build`：通过
- `npm run secret-scan`：通过，未发现明显密钥

开源 demo 结果：

```json
{
  "status": "demo_ready",
  "mode": "mock_open_source",
  "connector": "demo_connector",
  "scenarios": ["official_auth", "read_message", "read_lead", "customer_trial"]
}
```

真实 probe 无权限结果：

```json
{
  "status": "setup_required",
  "checks": [
    {"scenario": "official_auth", "status": "setup_required"},
    {"scenario": "read_message", "status": "setup_required"},
    {"scenario": "read_lead", "status": "setup_required"}
  ]
}
```

## 结论

如果目标是开源发布或演示，当前可以发布：系统主体、后台、运营流程、任务闭环、开源 mock connector 和真实 probe 脚本都已经具备。

如果目标是“生产真实平台验收 100% ready”，仍必须拿到客户/平台侧真实授权与样本；mock 脚本不能替代 `official_auth`、`read_message`、`read_lead` 的生产证据。

