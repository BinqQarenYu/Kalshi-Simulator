# Rule: App 3 (Autonomous Chef) Strict Firewall
# Role: Supervisor & Orchestrator

1. **Isolation**: Any agent assigned to pp_3_autonomous_chef is strictly forbidden from injecting logic into pp_1_machine_engine or pp_2_execution_bot codebases.
2. **Supervisor Contract**: App 3 orchestrates the system purely by monitoring logs, interacting with pp_2's configuration files (JSON/YAML), and triggering pp_1 retraining jobs via CLI or job queues. It does not trade directly.
3. **Failure Condition**: Any attempt to modify pp_1 or pp_2 python source code directly is a strict failure condition.
