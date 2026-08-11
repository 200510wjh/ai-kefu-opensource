# Open Source Connector Acceptance

This project has two acceptance modes for platform connectors.

## 1. Open-source demo mode

Use this when you do not have a real platform account, OAuth app, or read-only API permission.

```bash
npm run acceptance:open-source-demo
```

The script writes safe demo artifacts under:

```text
data/artifacts/open_source_connector_demo/
```

It covers the demo shape of:

- `official_auth`
- `read_message`
- `read_lead`
- `customer_trial`

Important boundary: this is not production evidence. It is for local development, CI smoke checks, screenshots, and open-source demos.

## 2. Real connector probe mode

Use this only after the customer or platform owner provides official read-only access.

Set environment variables:

```bash
REAL_CONNECTOR_NAME=douyin
REAL_CONNECTOR_ACCESS_TOKEN=<set in local shell only>
REAL_CONNECTOR_AUTH_HEADER="Authorization: Bearer {token}"
REAL_CONNECTOR_MESSAGES_URL=https://platform.example.com/messages
REAL_CONNECTOR_LEADS_URL=https://platform.example.com/leads
```

Run the probe:

```bash
npm run acceptance:real-connector
```

The script writes sanitized probe artifacts under:

```text
data/artifacts/real_connector_probe/
```

To also ingest sanitized samples into the SaaS connector read endpoints:

```bash
python scripts/real_connector_probe.py --ingest --app-base-url http://127.0.0.1:8000
```

## What Counts As Real Acceptance

Real production acceptance requires:

- `official_auth`: official OAuth/API credential or token exchange is actually configured.
- `read_message`: a real read-only message pull returns at least one usable message item.
- `read_lead`: a real read-only lead/customer pull returns at least one usable lead item.

The scripts never publish or send customer messages. They only read, sanitize, report, and optionally ingest data for human review.
