"""
Cleanup Redundant Documentation Script
Moves historical assessment batch reports into docs/09_REPORTS/assessments/
and removes redundant/superseded markdown files that have been fully
migrated into the docs/00_* through docs/10_* architecture.
"""
import os
import glob
import shutil
import subprocess

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 1. Target directory for historical assessments
ASSESSMENTS_DIR = os.path.join(REPO_DIR, "docs", "09_REPORTS", "assessments")
os.makedirs(ASSESSMENTS_DIR, exist_ok=True)

# 2. Move assessment files
assessment_files = glob.glob(os.path.join(REPO_DIR, "docs", "assessment_*.md"))
print(f"Moving {len(assessment_files)} assessment files to docs/09_REPORTS/assessments/...")
for src in assessment_files:
    fname = os.path.basename(src)
    dst = os.path.join(ASSESSMENTS_DIR, fname)
    shutil.move(src, dst)
print("Assessment move complete.")

# 3. Files to remove (fully integrated into docs/00_* to docs/10_*)
FILES_TO_REMOVE = [
    # Direct docs/ legacy files
    "docs/1_BOAT_3_WARRIORS_4_REGIONS_ARCHITECTURE.md",
    "docs/1_THREE_STEP_DOMINATION_BOT.md",
    "docs/2_DOMINION_2_BOT.md",
    "docs/3_MACRO_TREND_DOMINION_BOT.md",
    "docs/4_ONNX_MICROSTRUCTURE_BOT.md",
    "docs/API_REFERENCE.md",
    "docs/ARCHITECTURE.md",
    "docs/ASSET_HISTORY_ISOLATION.md",
    "docs/AUTONOMOUS_6_TRADE_IMPROVEMENT_CYCLE.md",
    "docs/aws_bot1v4_operational_capacity.md",
    "docs/aws_connection_integrity.md",
    "docs/AWS_deployment.md",
    "docs/BLEED_01_QUANT_COUNCIL_REASSESSMENT.md",
    "docs/DATA_INTEGRITY.md",
    "docs/DOF_Counterfactual_Shadow_Ledger.md",
    "docs/DOMINION_PARAMETERS_GUIDE.md",
    "docs/GeneralAssesment 001.md",
    "docs/GeneralAssesment 002.md",
    "docs/HANDOFF_SIMULATION_AND_POSTMORTEM.md",
    "docs/integration of kev ai.md",
    "docs/LANGGRAPH_COUNCIL_ORCHESTRATOR.md",
    "docs/market_condition_presets.md",
    "docs/MASTER_UI_UX_INVENTORY_AND_TERMINOLOGY_LEXICON.md",
    "docs/Overallcomponent of bot1v4.md",
    "docs/Overallcomponent of eth_bot1v4.md",
    "docs/POE_GROUND_TRUTH_SPECIFICATION.md",
    "docs/SCALEUP.md",
    "docs/STANDALONE_BOT_RUNBOOK.md",
    "docs/STORM_REGION_EMPIRICAL_PROOF.md",
    "docs/STRATEGY_BOTS.md",
    "docs/TRADING_GUIDE.md",
    "docs/TRADING_PIPELINE_WORKFLOW.md",
    # Root scratch/superseded files
    "1.md",
    "2.md",
    "3.md",
    "4.md",
    "Bet_Review_Improvement.md",
    "CONSTITUTION.md",
    "DEPLOYMENT.md",
    "MASTER_LIVE_BOT_TASK.md",
    "Question_Queries.md",
    # Legacy subfolder files
    "docs/audits/NIGHTLY_GOALS.md",
    "docs/audits/PERPETUAL_KAIZEN_JOURNAL.md",
    "docs/audits/SELF_HEALING_AUDIT.md",
    "docs/goals/PERPETUAL_APEX_GOAL.md",
    "docs/eth_bot1v4_components/experience_buffer.md",
    "docs/workflows/README.md",
    "docs/workflows/WF-001_data_pruning_and_gdrive_archival.md",
    "docs/workflows/WF-002_telemetry_distillation.md",
    "docs/workflows/WF-003_university_certification.md",
    "docs/workflows/WF-004_multi_bot_coordination.md",
    "docs/workflows/WF-005_jules_pr_fleet_consolidation.md",
    "docs/workflows/WF-006_autonomous_self_healing_sentinel.md",
    "scratch/lesson12.md",
]

removed_count = 0
for rel_path in FILES_TO_REMOVE:
    full_path = os.path.join(REPO_DIR, rel_path)
    if os.path.exists(full_path):
        os.remove(full_path)
        removed_count += 1
        print(f"Removed: {rel_path}")

print(f"Total redundant files removed: {removed_count}")

# 4. Remove empty legacy directories if empty
for dir_rel in ["docs/eth_bot1v4_components", "docs/goals", "docs/workflows"]:
    full_dir = os.path.join(REPO_DIR, dir_rel)
    if os.path.exists(full_dir) and not os.listdir(full_dir):
        os.rmdir(full_dir)
        print(f"Removed empty directory: {dir_rel}")
