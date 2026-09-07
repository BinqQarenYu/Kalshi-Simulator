## 2025-05-18 - Input Sanitization & Path Traversal Prevention on Export Endpoints
**Vulnerability:** The `/api/export/ticks` endpoint accepted an unvalidated `timeframe` string parameter in `glob(f"ticks_{timeframe}_*.jsonl")`, allowing potential path traversal and wildcard pattern injection.
**Learning:** File globbing against user-supplied query parameters on file-serving endpoints can expose directory traversal risks or unexpected file access if parameters are not strictly validated against an allowed character set.
**Prevention:** Strictly sanitize input parameters with regex (e.g. `^[a-zA-Z0-9_\-]+$`), resolve file paths, and assert `target_file.is_relative_to(data_dir)` before serving files with `FileResponse`.
