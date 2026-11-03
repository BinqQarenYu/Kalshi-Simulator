import sys
from pathlib import Path

target_file = Path("src/kalshi_sim/ml/onnx_engine.py")
content = target_file.read_text(encoding="utf-8")

old_handler = 'file_handler = logging.FileHandler(str(log_path), mode="a", encoding="utf-8")'
new_handler = 'file_handler = RotatingFileHandler(str(log_path), maxBytes=5 * 1024 * 1024, backupCount=2, encoding="utf-8")'

if old_handler in content:
    content = content.replace(old_handler, new_handler)
    if "from logging.handlers import RotatingFileHandler" not in content:
        content = "from logging.handlers import RotatingFileHandler\n" + content
    target_file.write_text(content, encoding="utf-8")
    print("SUCCESS: Updated onnx_engine.py with RotatingFileHandler")
else:
    print("WARNING: Target string not found or already updated")
