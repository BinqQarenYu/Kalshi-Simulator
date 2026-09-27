import re

file_path = 'src/kalshi_sim/routers/perpetuals.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace float(x) with Decimal(str(x)) in calculation context
content = re.sub(r'float\(([^)]+)\)', r'Decimal(str(\1))', content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
