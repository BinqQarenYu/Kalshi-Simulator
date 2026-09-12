---
trigger: always_on
glob: "**/*"
description: CFTC statutory compliance, wash-trading prevention, anti-spoofing, and API security invariants.
---

# 3. CFTC Regulatory Compliance & API Security

## 1. Zero Tolerance for Wash Trading
- Never submit an order that matches or crosses with an existing open/resting order from the same account.
- Immediate pre-trade check: reject and log any opposing resting order at same/crossing price.
- **Multi-Bot Self-Crossing Shield**: When multiple autonomous bots run concurrently, all trade submissions must be arbitrated synchronously by `LiveCoordinator`. If Bot A holds an active YES on a market, Bot B is strictly prohibited from submitting NO on the same ticker, eliminating CFTC Section 4c(a)(1) wash-trading liability.

## 2. Zero Tolerance for Spoofing & Layering
- Never submit phantom orders or rapid cancellation floods intended to manipulate order book depth.
- Maintain Order-to-Trade Ratio (OTR) under strict regulatory safety thresholds.

## 3. Cryptographic Key & Secret Isolation
- Never log, stream, expose, or commit private RSA keys (`.pem`), API keys, or raw authentication signatures into git, client bundles, or public logs.

## 4. Rate Limiting & Graceful Backoff
- Adhere to token-bucket rate limits ($20\text{ req/s}$ public, $30\text{ req/s}$ authenticated).
- Implement exponential backoff when encountering HTTP 429.
