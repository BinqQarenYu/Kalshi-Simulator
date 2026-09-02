# Sentinel's Journal

## 2026-03-01 - Hardcoded Fallback API Key ID in Server State Initialization
**Vulnerability:** A hardcoded Kalshi API key UUID was provided as a fallback default when `KALSHI_API_KEY_ID` environment variable was not set (`os.getenv("KALSHI_API_KEY_ID", "50fb3c25-...")`).
**Learning:** Default parameter fallbacks in `os.getenv()` can inadvertently expose sensitive credentials or leak production/demo API key IDs into source code.
**Prevention:** Always retrieve credentials from environment variables without hardcoded string defaults (`os.getenv("KALSHI_API_KEY_ID")`), ensuring missing configuration safely yields `None`.
