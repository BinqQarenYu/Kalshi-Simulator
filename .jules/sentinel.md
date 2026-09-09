## 2026-09-08 - Disable Unverified SSL Context Fallbacks in Financial Exchange Connectors
**Vulnerability:** `get_ssl_context()` fell back to `ssl._create_unverified_context()` if system CA certificate stores and `certifi` failed, disabling TLS certificate verification on live exchange REST and WebSocket connections.
**Learning:** Resilient network fallbacks should never sacrifice cryptographic verification. In financial trading platforms, disabling SSL verification opens outgoing requests and API credentials to Man-In-The-Middle (MITM) attacks.
**Prevention:** Always fail securely by raising an exception when secure SSL/TLS context creation fails rather than falling back to unverified contexts.
