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

    def _load_vault_axiom(self, category: str) -> str:
        vault_path = Path("data/immutable_truth_vault.json")
        if not vault_path.exists():
            return "STRICT_DECIMAL_ONLY: Use Decimal for all monetary math. Zero float tolerance."
        try:
            data = json.loads(vault_path.read_text(encoding="utf-8"))
            if "FLOAT" in category or "DIVISION" in category:
                ax = data.get("tier_0_math_axioms", {}).get("AXIOM_0_1_DECIMAL_ONLY", {})
                return f"{ax.get('name')}: {ax.get('description')}"
            elif "BOUNDARY" in category or "SINGULARITY" in category:
                ax = data.get("tier_0_math_axioms", {}).get("AXIOM_0_3_EXPIRATION_SINGULARITY", {})
                return f"{ax.get('name')}: {ax.get('description')}"
            elif "WASH" in category or "CANNIBAL" in category:
                ax = data.get("tier_1_regulatory_invariants", {}).get("AXIOM_1_1_CFTC_ANTI_WASH", {})
                return f"{ax.get('name')}: {ax.get('description')}"
            return "GENERAL_INVARIANT: Adhere strictly to institutional quantitative truth math."
        except Exception:
            return "STRICT_DECIMAL_ONLY: Zero float tolerance on financial numbers."

    def review_suspect_math(self, file_path: str, line_no: int, snippet: str, concern: str) -> Optional[Dict[str, Any]]:
        """
        Sends an isolated micro-snippet to Lead Deer (Gemini 3.6 Flash) bound by the Citadel Truth Vault.
        """
        if not self._check_rate_limit():
            return {"status": "RATE_LIMITED", "reason": "Exceeded 2 calls/hour token armor limit"}

        axiom_constraint = self._load_vault_axiom(concern)

        prompt = f"""You are LEAD DEER, an adversarial quantitative proof reviewer legally bound by the CITADEL TRUTH VAULT.

MANDATORY TRUTH INVARIANT:
[{axiom_constraint}]

TARGET SNIPPET TO AUDIT:
FILE: {file_path} (Line {line_no})
CONCERN: {concern}
```python
{snippet}
```

ADVERSARIAL MISSION:
Evaluate strictly against the Mandatory Truth Invariant above.
If the code violates this invariant or contains IEEE-754 precision drift, mark is_fatal=true and give a <=3 line Decimal fix.
If mathematically safe and non-violating, mark is_fatal=false.

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
            from google import genai

            client = genai.Client(api_key=api_key)
            resp = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt,
            )
            raw_text = resp.text.strip() if resp.text else ""

            # Clean json fences if present
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
    reviewer = LeadDeerReviewer()
    print("[*] Testing Lead Deer Token-Armor Reviewer...")
    test_result = reviewer.review_suspect_math(
        "strategies/demo.py", 42, "pnl = (exit_price - entry_price) / entry_price", "FLOAT_DIVISION_RISK"
    )
    print("[+] Lead Deer Verdict:", json.dumps(test_result, indent=2))
