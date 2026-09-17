"""
deer_architect_reviewer.py — Deer Architect UI/UX Ergonomics Reviewer
Autonomous reviewer for institutional WebCLOB ergonomics, contrast, glanceable telemetry, and typography.
Enforces Token-Armor: micro-payloads, strict JSON schema, max 2 calls/hour.
"""

import os
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional

TOKEN_THROTTLE_FILE = Path("docs/audits/deer_architect_throttle.json")
MAX_CALLS_PER_HOUR = 2


class DeerArchitectReviewer:
    def __init__(self, deerflow_env_path: Path = Path("F:/012A_Github/deer-flow/.env")):
        self.deerflow_env_path = deerflow_env_path
        self._ensure_throttle_db()

    def _ensure_throttle_db(self):
        if not TOKEN_THROTTLE_FILE.parent.exists():
            TOKEN_THROTTLE_FILE.parent.mkdir(parents=True, exist_ok=True)
        if not TOKEN_THROTTLE_FILE.exists():
            TOKEN_THROTTLE_FILE.write_text(json.dumps({"timestamps": []}), encoding="utf-8")

    def _check_rate_limit(self) -> bool:
        try:
            data = json.loads(TOKEN_THROTTLE_FILE.read_text(encoding="utf-8"))
            now = time.time()
            valid_ts = [ts for ts in data.get("timestamps", []) if now - ts < 3600]
            if len(valid_ts) >= MAX_CALLS_PER_HOUR:
                return False
            valid_ts.append(now)
            TOKEN_THROTTLE_FILE.write_text(json.dumps({"timestamps": valid_ts}), encoding="utf-8")
            return True
        except Exception:
            return False

    def review_ui_ergonomics(self, file_path: str, line_no: int, snippet: str, concern: str) -> Optional[Dict[str, Any]]:
        """
        Sends an isolated UI micro-snippet to Deer Architect (Gemini 3.6 Flash) bound by Article VI.
        """
        if not self._check_rate_limit():
            return {"status": "RATE_LIMITED", "reason": "Exceeded 2 calls/hour token armor limit"}

        prompt = f"""You are DEER ARCHITECT, Principal Fintech UI/UX Designer bound by ARTICLE VI of CONSTITUTION.MD.

MANDATORY UI/UX CONSTITUTIONAL INVARIANTS:
1. Glanceable Telemetry: Tabular numerals (font-mono tabular-nums) for all financial numbers, timers, prices, PnL.
2. WebCLOB Dark Theme: Institutional dark void palette (#0c0f12, slate-900/950, emerald/crimson/amber).
3. Zero Logic Tampering: Strictly NO changes to useState, useEffect, useRef, or trading handlers.

TARGET UI SNIPPET TO AUDIT:
FILE: {file_path} (Line {line_no})
CONCERN: {concern}
```tsx
{snippet}
```

MISSION:
Evaluate the snippet for visual polish, font-mono tabular-nums, or ergonomic clarity.
Never alter logic or component props.
If an improvement is needed, set needs_improvement=true and give a clean minimal JSX/Tailwind fix.

RESPOND STRICTLY IN VALID JSON:
{{
  "needs_improvement": true/false,
  "critique": "one concise sentence",
  "recommended_fix": "jsx/tailwind snippet or empty string"
}}
"""
        try:
            from dotenv import load_dotenv
            load_dotenv(self.deerflow_env_path)
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                return {"status": "ERROR", "reason": "No GEMINI_API_KEY found in .env"}

            import truststore
            truststore.inject_into_ssl()
            from google import genai

            client = genai.Client(api_key=api_key)
            resp = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt,
            )
            raw_text = resp.text.strip() if resp.text else ""

            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            elif raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]

            return json.loads(raw_text.strip())
        except Exception as e:
            return {"status": "ERROR", "reason": str(e)}


if __name__ == "__main__":
    reviewer = DeerArchitectReviewer()
    print("[*] Testing Deer Architect Token-Armor Reviewer...")
    test_result = reviewer.review_ui_ergonomics(
        "frontend/src/components/BabyBotConsole.tsx", 2100,
        '<span className="text-emerald-400 font-bold">$52.00</span>', "MISSING_TABULAR_NUMS"
    )
    print("[+] Deer Architect Verdict:", json.dumps(test_result, indent=2))
