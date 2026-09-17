"""
lead_deer_reviewer.py — Lead Deer Adversarial Falsification Reviewer
Queries Google Gemini via DeerFlow's direct backend or bridge to falsify code hypotheses.
Enforces Token-Armor: micro-payloads, strict JSON schema, <=2 calls/hour.
"""

import os
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional

TOKEN_THROTTLE_FILE = Path("docs/audits/lead_deer_throttle.json")
MAX_CALLS_PER_HOUR = 2


class LeadDeerReviewer:
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
            # Keep only timestamps within the last 3600 seconds (1 hour)
            valid_ts = [ts for ts in data.get("timestamps", []) if now - ts < 3600]
            if len(valid_ts) >= MAX_CALLS_PER_HOUR:
                return False
            valid_ts.append(now)
            TOKEN_THROTTLE_FILE.write_text(json.dumps({"timestamps": valid_ts}), encoding="utf-8")
            return True
        except Exception:
            return False

    def review_suspect_math(self, file_path: str, line_no: int, snippet: str, concern: str) -> Optional[Dict[str, Any]]:
        """
        Sends an isolated micro-snippet to Lead Deer (Gemini 3.6 Flash) under adversarial falsification.
        """
        if not self._check_rate_limit():
            return {"status": "RATE_LIMITED", "reason": "Exceeded 2 calls/hour token armor limit"}

        prompt = f"""You are LEAD DEER, an adversarial quantitative proof reviewer.
Evaluate this suspect Python code snippet from an institutional trading terminal:

FILE: {file_path} (Line {line_no})
CONCERN: {concern}
SNIPPET:
```python
{snippet}
```

ADVERSARIAL MISSION:
Your sole goal is to FALSIFY this code. Find if it contains a real mathematical, numerical, or boundary flaw (e.g. IEEE 754 float drift, division by zero at T->0, negative variance).
If it is mathematically sound or non-fatal, mark is_fatal=false.
If fatal, provide a minimal <=5 line fix using Python Decimal.

RESPOND STRICTLY IN VALID JSON:
{{
  "is_fatal": true/false,
  "flaw_explanation": "one clear sentence",
  "minimal_fix": "python code snippet or empty string"
}}
"""
        # Execute invocation via DeerFlow backend runner
        try:
            from dotenv import load_dotenv
            load_dotenv(self.deerflow_env_path)
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                return {"status": "ERROR", "reason": "No GEMINI_API_KEY found in .env"}

            import truststore
            truststore.inject_into_ssl()
            from langchain_google_genai import ChatGoogleGenerativeAI

            llm = ChatGoogleGenerativeAI(model="gemini-3.6-flash", api_key=api_key, max_tokens=300)
            res = llm.invoke(prompt)
            
            raw_text = res.content
            # Handle list-wrapped content if returned by langchain
            if isinstance(raw_text, list) and raw_text:
                raw_text = raw_text[0].get("text", "")

            # Clean json fences if present
            raw_text = raw_text.strip()
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]

            return json.loads(raw_text.strip())
        except Exception as e:
            return {"status": "ERROR", "reason": str(e)}


if __name__ == "__main__":
    reviewer = LeadDeerReviewer()
    print("[*] Testing Lead Deer Token-Armor Reviewer...")
    test_result = reviewer.review_suspect_math(
        "strategies/demo.py", 42, "pnl = (exit_price - entry_price) / entry_price", "FLOAT_DIVISION_RISK"
    )
    print("[+] Lead Deer Verdict:", json.dumps(test_result, indent=2))
