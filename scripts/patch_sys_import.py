with open('src/kalshi_sim/ml/onnx_engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_import = """import os
import shutil"""

new_import = """import os
import shutil
import sys"""

if old_import in content:
    content = content.replace(old_import, new_import, 1)
    with open('src/kalshi_sim/ml/onnx_engine.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("SUCCESS: Added import sys to onnx_engine.py")
else:
    print("FAILED: old_import not found")
