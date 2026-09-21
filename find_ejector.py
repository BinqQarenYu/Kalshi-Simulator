with open('src/kalshi_sim/ml/domination_bot.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'Rule 6' in line or 'Valley Ejector' in line:
        start = max(0, i - 5)
        end = min(len(lines), i + 35)
        print(f"--- Found at line {i+1} ---")
        for j in range(start, end):
            print(f'{j+1}: {lines[j].rstrip()}')
        break
