# ZOHAIR PO3 AI AGENT

Backend starter for receiving TradingView XAUUSD M5 alerts. This service validates signal structure and approximate 2R risk/reward, then stores received signals.

**Alerts and analysis only. It does not place trades or predict market direction.**

## Deploy on Render

1. Open Render and sign in.
2. Choose **New + → Blueprint**.
3. Connect the GitHub repository `zohair7777/zohair-po3-ai-agent`.
4. Render reads `render.yaml`; confirm deployment.
5. In the service environment settings, keep the generated `AGENT_SECRET` private.
6. After deployment, check `https://YOUR-SERVICE.onrender.com/health`.

Webhook URL format:

`https://YOUR-SERVICE.onrender.com/webhook/tradingview/YOUR_AGENT_SECRET`

## Important

The starter uses SQLite. Free hosting filesystems may be temporary, so stored signals can be lost after restarts or redeploys. Use managed PostgreSQL for durable history.

A `RECEIVED` response means the payload passed basic format, direction, level, timestamp, and approximate 2R checks. It is not independent market confirmation.
