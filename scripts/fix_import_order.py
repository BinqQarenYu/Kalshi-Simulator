from pathlib import Path

target_file = Path("src/kalshi_sim/ml/onnx_engine.py")
content = target_file.read_text(encoding="utf-8")

# Remove top import if present
if content.startswith("from logging.handlers import RotatingFileHandler\n"):
    content = content[len("from logging.handlers import RotatingFileHandler\n"):]

# Ensure from logging.handlers import RotatingFileHandler is right after import logging
content = content.replace("import logging\n", "import logging\nfrom logging.handlers import RotatingFileHandler\n")

target_file.write_text(content, encoding="utf-8")
print("FIXED: Moved RotatingFileHandler import below __future__")
