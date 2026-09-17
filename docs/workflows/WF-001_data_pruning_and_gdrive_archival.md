# WF-001: Cold Data Pruning & Google Drive Archiving

## 1. Executive Summary & Purpose
In high-frequency binary options trading, local order book logging produces massive volumes of text data (~15 GB/day across 20Hz ticks and L2 streams). Unchecked, the local `data/` folder will grow past 100+ GB, risking disk-full crashes during live trading.

**WF-001 establishes an automated cold-storage tiering process:**
1. Purges empty 0-byte aborted log files.
2. Segregates files by age:
   - **Hot Tier ($\le 48$ Hours):** Kept uncompressed on local SSD for continuous neural network retraining and immediate backtesting.
   - **Cold Tier (> 48 Hours):** High-ratio Gzip compression into `.tar.gz` archives in `data/archives/`.
3. Directly syncs the compressed archive to your 5 TB Google Drive (`I:\My Drive\Kalshi Repo Data\`).
4. Verifies SHA-256 integrity before pruning the local uncompressed cold files, instantly reclaiming **75+ GB** of SSD space.

---

## 2. Invariants & Safety Armoring

> [!CAUTION]
> The following files and directories are **strictly protected** and must NEVER be deleted, moved, or altered:
> - `data/bot_parameters_domination.json` (Active strategy parameters)
> - `data/seal_of_excellence.json` (Cryptographic live trading authorization)
> - `data/win_loss_reports.json` (Realized PnL & historical settlements)
> - `data/kalshi_sim.db` (SQLite ledger)
> - `data/presets/*` (Sanctioned baseline configurations)
> - `data/incubator_state.json` (Candidate bot training records)
> - All tick files with age $\le 48$ hours.

---

## 3. Operational Execution

### Quick Audit (Zero Changes)
To inspect the disk state and see hot vs. cold breakdown:
```bash
python -m kalshi_sim.archival_engine --audit
```

### Run Archival, GDrive Sync & Prune
To compress cold files, upload to Google Drive, and reclaim SSD space:
```bash
python -m kalshi_sim.archival_engine --archive
```

### Local Compression Only (No GDrive copy)
If Google Drive is offline or not mounted:
```bash
python -m kalshi_sim.archival_engine --archive --no-gdrive
```

---

## 4. How to Restore / Extract Historical Data
If you ever need to restore archived cold data for a long-range backtest:
1. Open PowerShell in `f:\012D_TRADE\Kalshi Simulator\data`.
2. Extract the target archive:
   ```bash
   tar -xvzf archives/kalshi_ticks_archive_sep2026.tar.gz
   ```
3. Run your backtester or simulation on the extracted files.
