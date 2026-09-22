# Institutional Workflow Registry

Master index of standardized operational workflows for the Kalshi algorithmic trading terminal. Each workflow defines its operational triggers, executing agents, safety invariants, and execution commands.

---

## 📋 Catalog of Registered Workflows

| Workflow ID | Workflow Name | Lead Agent | Operational Scope | Documentation |
| :--- | :--- | :--/: | :--- | :--- |
| **WF-001** | **Cold Data Pruning & Google Drive Archiving** | 🦌 DEER & 🏇Quoquo | Compresses raw ticks (>48h), purges 0-byte logs, syncs aichive to 5 TB Google Drive, and frees 75+ GB SSD. | [WF-001 Guide](./WF-001_data_pruning_and_gdrive_archival.md) |
| **WF-002** | **Continuous Telemetry Distillation (Warm Path)** | 🦌 DEER & 🏇Quoquo | Post-cycle log scrubbing, 92-token forensic summaries, and Quoquo Vault deposits. | [WF-002 Guide](./WF-002_telemetry_distillation.md) |
| **WF-003** | **Quant University Candidate Matriculation & Seal Gauntlet** | 🏓 Formal Incubator | 30-cycle shadow training, GPA scorecard, and 5-Pillar Seal of Excellence gauntlet. | [WF-003 Guide](./WF-003_university_certification.md) |
| **WF-004** | **Multi-Bot Live Concurrency & Anti-Wash Arbitration** | 🊛️ LiveCoordinator | Synchronous pre-trade gatekeeper enforcing CFTC wash-trading immunity and 1-trade locks. | [WF-004 Guide](./WF-004_multi_bot_coordination.md) |
| **WF-005** | **Automated Jules PR Fleet Consolidation & Verification** | 🦌 DEER, 🧇Boko, 🏇Quoquo | Sequential batching, test gating, decimal math isolation, and Jules PRs audit. | [WF-005 Guide](./WF-005_jules_pr_fleet_consolidation.md) |
| **WF-006** | **Autonomous Self-Healing & Self-Review Sentinel** | 🦌 Lead Deer, 🛡️ Koko, ⚡ Codeflow | Continuous 24/7 AST flaw detection, SymPy truth of math, adversarial proof, and live sanctuary. | [WF-006 Guide](./WF-006_autonomous_self_healing_sentinel.md) |

---

## 🛹 Usage Guidelines
1. **Naming Standard**: All workflows follow `WF-XXX_short_name.md`.
2. **Deterministic Invariants**: Every workflow must document its protected files and non-negotiable invariants.
3. **Execution Commands**: CLI and API triggers must be explicitly documented with expected inputs and outputs.
