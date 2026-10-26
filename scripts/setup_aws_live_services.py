import subprocess

s_bot = """[Unit]
Description=Kalshi Bot 1 V4 (Quolas) Autonomous Headless Quantitative Engine
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/kalshi-bot
ExecStart=/home/ec2-user/kalshi-bot/venv/bin/python aws_headless_daemon.py
Restart=always
RestartSec=5
Environment=PYTHONPATH=/home/ec2-user/kalshi-bot/src
Environment=KALSHI_CLOUD_LEAN=true
Environment=KALSHI_ENV=live
Environment=KALSHI_MODE=live
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""

s_btc = """[Unit]
Description=Kalshi BTC Bot 1 V4 (Bitcoin Domination) Autonomous Live Engine
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/kalshi-bot
ExecStart=/home/ec2-user/kalshi-bot/venv/bin/python src/kalshi_sim/ml/btc_bot1v4/paper_trade_btcbot.py --mode live --cycle-interval 5
Restart=always
RestartSec=5
Environment=PYTHONPATH=/home/ec2-user/kalshi-bot/src
Environment=KALSHI_CLOUD_LEAN=true
Environment=KALSHI_ENV=live
Environment=KALSHI_MODE=live
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""

s_eth = """[Unit]
Description=Kalshi ETH Bot 1 V4 (Ethereum Domination) Autonomous Live Engine
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/kalshi-bot
ExecStart=/home/ec2-user/kalshi-bot/venv/bin/python src/kalshi_sim/ml/eth_bot1v4/paper_trade_ethbot.py --mode live --cycle-interval 5
Restart=always
RestartSec=5
Environment=PYTHONPATH=/home/ec2-user/kalshi-bot/src
Environment=KALSHI_CLOUD_LEAN=true
Environment=KALSHI_ENV=live
Environment=KALSHI_MODE=live
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""

s_bnb = """[Unit]
Description=Kalshi BNB Bot 1 V4 (Binance Coin Domination) Autonomous Live Engine
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/kalshi-bot
ExecStart=/home/ec2-user/kalshi-bot/venv/bin/python src/kalshi_sim/ml/bnb_bot1v4/paper_trade_bnbbot.py --mode live
Restart=always
RestartSec=5
Environment=PYTHONPATH=/home/ec2-user/kalshi-bot/src
Environment=KALSHI_CLOUD_LEAN=true
Environment=KALSHI_ENV=live
Environment=KALSHI_MODE=live
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""

with open("/tmp/kalshi-bot.service", "w") as f:
    f.write(s_bot)
with open("/tmp/kalshi-btc-bot.service", "w") as f:
    f.write(s_btc)
with open("/tmp/kalshi-eth-bot.service", "w") as f:
    f.write(s_eth)
with open("/tmp/kalshi-bnb-bot.service", "w") as f:
    f.write(s_bnb)

subprocess.run(["sudo", "mv", "/tmp/kalshi-bot.service", "/etc/systemd/system/kalshi-bot.service"], check=True)
subprocess.run(["sudo", "mv", "/tmp/kalshi-btc-bot.service", "/etc/systemd/system/kalshi-btc-bot.service"], check=True)
subprocess.run(["sudo", "mv", "/tmp/kalshi-eth-bot.service", "/etc/systemd/system/kalshi-eth-bot.service"], check=True)
subprocess.run(["sudo", "mv", "/tmp/kalshi-bnb-bot.service", "/etc/systemd/system/kalshi-bnb-bot.service"], check=True)
subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
subprocess.run(["sudo", "systemctl", "enable", "kalshi-bot.service", "kalshi-btc-bot.service", "kalshi-eth-bot.service", "kalshi-bnb-bot.service"], check=True)
print("✅ LIVE SERVICE CONFIGURATION (BTC, ETH, BNB) COMPLETED SUCCESSFULLY")
