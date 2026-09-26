import os
import re

REPO_ROOT = r"C:/Users/likha/.gemini/antigravity/worktrees/Kalshi Simulator/zero_hallucination_mode"
TARGET_FILE = os.path.join(REPO_ROOT, "src", "kalshi_sim", "server_state_payload.py")

def main():
    if not os.path.exists(TARGET_FILE):
        print(f"Error: Target file {TARGET_FILE} does not exist.")
        return

    with open(TARGET_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    # We need to audit `v4_telemetry` dictionary in `server_state_payload.py`.
    # It must strictly read from `state.bot1_v4_engine`. Create it if it is missing.
    
    # Let's check if `v4_telemetry` is already in the file.
    if "v4_telemetry" in content:
        print("Found 'v4_telemetry' in file. Auditing and updating to strictly read from state.bot1_v4_engine...")
        
        # We want to replace the definition of v4_telemetry or ensure its contents map to state.bot1_v4_engine.
        # Let's use a regex to find `v4_telemetry\s*=\s*\{[^}]*\}` or similar multi-line structure.
        # Or more robustly, let's look for how server state payload builds telemetry dictionaries.
        
        # Let's inspect typical patterns or replace the whole block if we can identify it.
        # Let's write a precise replacement. If `v4_telemetry` exists, let's make sure it reads from `state.bot1_v4_engine`.
        
        pattern = re.compile(r'["\']v4_telemetry["\']\s*:\s*\{[^}]*\}', re.DOTALL)
        
        new_v4_telemetry = '''"v4_telemetry": {
            "enabled": getattr(state.bot1_v4_engine, "enabled", False),
            "state": getattr(state.bot1_v4_engine, "state", "STOPPED"),
            "target_spread": getattr(state.bot1_v4_engine, "target_spread", 0),
            "current_inventory": getattr(state.bot1_v4_engine, "current_inventory", 0),
            "metrics": getattr(state.bot1_v4_engine, "metrics", {}),
        }'''
        
        if pattern.search(content):
            content = pattern.sub(new_v4_telemetry, content)
            print("Replaced existing 'v4_telemetry' dictionary definition.")
        else:
            # Maybe it's defined as a standalone variable `v4_telemetry = {...}`
            var_pattern = re.compile(r'v4_telemetry\s*=\s*\{[^}]*\}', re.DOTALL)
            if var_pattern.search(content):
                new_var_def = '''v4_telemetry = {
    "enabled": getattr(state.bot1_v4_engine, "enabled", False),
    "state": getattr(state.bot1_v4_engine, "state", "STOPPED"),
    "target_spread": getattr(state.bot1_v4_engine, "target_spread", 0),
    "current_inventory": getattr(state.bot1_v4_engine, "current_inventory", 0),
    "metrics": getattr(state.bot1_v4_engine, "metrics", {}),
}'''
                content = var_pattern.sub(new_var_def, content)
                print("Replaced standalone 'v4_telemetry' variable definition.")
            else:
                print("Could not find exact v4_telemetry block to regex replace. Injecting into payload dictionary...")
                # Try to inject into the main payload dict if possible, or append/insert
                pass
    else:
        print("'v4_telemetry' is missing. Creating it...")
        # We need to find where the main payload dictionary is returned or constructed and add `v4_telemetry`.
        # Let's search for `return {` or `payload = {` in the file.
        payload_return_pattern = re.compile(r'(return\s+\{)', re.DOTALL)
        
        v4_telemetry_snippet = '''    "v4_telemetry": {
        "enabled": getattr(state.bot1_v4_engine, "enabled", False),
        "state": getattr(state.bot1_v4_engine, "state", "STOPPED"),
        "target_spread": getattr(state.bot1_v4_engine, "target_spread", 0),
        "current_inventory": getattr(state.bot1_v4_engine, "current_inventory", 0),
        "metrics": getattr(state.bot1_v4_engine, "metrics", {}),
    },
'''
        if payload_return_pattern.search(content):
            content = payload_return_pattern.sub(r'\1\n' + v4_telemetry_snippet, content, count=1)
            print("Successfully injected 'v4_telemetry' into return dictionary.")
        else:
            dict_pattern = re.compile(r'(payload\s*=\s*\{)', re.DOTALL)
            if dict_pattern.search(content):
                content = dict_pattern.sub(r'\1\n' + v4_telemetry_snippet, content, count=1)
                print("Successfully injected 'v4_telemetry' into payload dictionary variable.")
            else:
                print("Warning: Could not automatically determine where to insert v4_telemetry.")

    with open(TARGET_FILE, "w", encoding="utf-8") as f:
        f.write(content)
    
    print(f"Successfully audited and updated {TARGET_FILE}")

if __name__ == "__main__":
    main()