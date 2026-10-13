with open('/home/ec2-user/kalshi-bot/quolas_24_7.log', 'r', encoding='utf-8', errors='ignore') as f:
    for line in f:
        if "[LIVE BOT 1 V4]" in line or "Frozen sensor" in line or "running in STUB mode" in line:
            print(line.rstrip())
