import glob, json

files = sorted(glob.glob('data/ticks_paper_live_*.jsonl'))[-10:]
counts = {}
for f in files:
    for line in open(f, encoding='utf-8'):
        try:
            d = json.loads(line)
            r = d.get('ai_rationale')
            if r:
                prefix = r.split(':')[0]
                counts[prefix] = counts.get(prefix, 0) + 1
        except Exception as e:
            pass

for k, v in sorted(counts.items(), key=lambda x: -x[1]):
    print(f"{v}: {k}")
