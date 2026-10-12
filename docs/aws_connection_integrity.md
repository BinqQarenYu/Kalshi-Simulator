# aws_connection_integrity.md — AWS Free Tier Headless Appliance Specification

**Document ID:** `docs/aws_connection_integrity.md`  
**Classification:** Cloud Infrastructure & Compliance Blueprint  
**Target Engine:** Bot 1 V4 (`quolas.onnx` only, strictly Kalshi BTC 15m/5m contracts)  
**Target Hardware:** AWS EC2 `t3.micro` (Amazon Linux 2023, 1 vCPU, 1 GB RAM, 8 GB EBS SSD)  
**Status:** Approved Formulation & Granular Execution Tracker  

---

## 1. AWS Free Tier & AUP Compliance Invariants

| Category | Policy / Limit | Appliance Architecture Strategy | Compliance Status |
| :--- | :--- | :--- | :--- |
| **Compute Budget** | 750 hours/month Free Tier | 1 single `t3.micro` instance running 24/7 | **100% Compliant ($0.00/mo)** |
| **RAM Ceiling** | 1.0 GB Physical RAM | Headless daemon (~110 MB RAM) + 1.0 GB Swap file | **Zero OOM Risk** |
| **Disk Storage** | 30.0 GB EBS Allocation | Current volume is 8.0 GB; data footprint capped at < 500 MB | **100% Compliant** |
| **Data Egress** | 100 GB/month Free Egress | Inbound tick feeds free; outbound orders/telemetry < 2 GB/mo | **100% Compliant** |
| **CPU Credit Burn** | `t3.micro` baseline 10% credit | Ultra-low ONNX inference (< 5% CPU). Heavy training stays on PC | **Zero Throttling Risk** |
| **Acceptable Use** | No Port Scanning / Flooding | `AgentLawOrder` Token Bucket: 30 req/sec rate limit ceiling | **100% AUP Compliant** |

---

## 2. Fatal Failure Modes & Root-Cause Remediations

1. **Failure Mode 1: Disk Overfill Crash (119 GB Raw Log Exhaustion)**
   - *Root Cause:* Historical tick archives (`data/*.jsonl`) exhaust the 8 GB cloud drive within minutes.
   - *Remediation:* Deploy `aws_prune_guard.py` to suppress raw tick writing on EC2; retain only rolling trade receipts and JSON database registries.
2. **Failure Mode 2: Kernel Out-Of-Memory (OOM) Process Termination**
   - *Root Cause:* Sudden memory spikes above 900 MB cause the Linux kernel OOM killer to terminate the Python process.
   - *Remediation:* Provision a 1.0 GB Swap File (`/swapfile`) on Amazon Linux 2023.
3. **Failure Mode 3: `NameError: name 'upside_thresh' is not defined`**
   - *Root Cause:* Unintentional omission during dual-regime chop armor commit in [`src/kalshi_sim/ml/domination_exit_evaluator.py`](file:///F:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/ml/domination_exit_evaluator.py).
   - *Remediation:* Restore `upside_thresh = getattr(bot, "upside_capture_ratio_threshold", 0.50)` at line 425.
4. **Failure Mode 4: Headless Display Absence Crash**
   - *Root Cause:* Tkinter / Matplotlib UI calls fail on Linux servers lacking an X11 display server.
   - *Remediation:* Deploy headless execution runner (`aws_headless_runner.py`) running pure asyncio event loop and FastAPI WebCLOB without desktop window dependencies.

---

## 3. Quolas Model Sync & Hot-Swap Architecture

- **Scope:** Exclusively `quolas.onnx` (140 KB). Gold models and other architectures are completely bypassed.
- **In-Memory Hot-Swap:** Daemon checks SHA-256 hash of `models/quolas.onnx`. When a newly retrained model is uploaded from the local PC, the active ONNX inference session is reloaded atomically in memory without interrupting cycles or dropping active trades.

---

## 4. Granular Task Execution Plan

- [ ] **Phase 1: Fatal Bug Resolution & Code Integrity Verification**
  - [ ] Restore `upside_thresh` in [`src/kalshi_sim/ml/domination_exit_evaluator.py`](file:///F:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/ml/domination_exit_evaluator.py).
  - [ ] Execute targeted unit tests to verify doubt-harvest profit evaluation passes cleanly.
- [ ] **Phase 2: Lean AWS Server Preparation (Remote EC2 Execution)**
  - [ ] Provision 1.0 GB swap file on `13.63.158.94`.
  - [ ] Install minimal runtime dependencies: `python3`, `python3-pip`, `tmux`.
- [ ] **Phase 3: Clean Deployment Packaging & Transfer**
  - [ ] Stage strictly essential assets: `src/`, `models/quolas.onnx`, `keys/`, `.env`, `requirements.txt`, `data/*.json`.
  - [ ] Upload clean staging bundle to EC2 via SCP (zero multi-gigabyte tick logs).
- [ ] **Phase 4: 24/7 Service Daemon Setup & Telemetry Verification**
  - [ ] Configure `kalshi-quolas.service` systemd unit or persistent `tmux` session.
  - [ ] Verify live engine initialization, Kalshi API connection, and quolas ONNX inference.
