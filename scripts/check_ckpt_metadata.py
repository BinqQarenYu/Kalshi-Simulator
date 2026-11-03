import subprocess

cmd = [
    'ssh', '-i', 'kalshi_aws_key.pem',
    '-o', 'StrictHostKeyChecking=no',
    'ec2-user@13.63.158.94',
    '/home/ec2-user/kalshi-bot/venv/bin/python -c "import torch; ckpt = torch.load(\x27/home/ec2-user/kalshi-bot/models/best_model.pt\x27, map_location=\x27cpu\x27); print({k: v for k, v in ckpt.items() if k != \x27model_state_dict\x27 and k != \x27optimizer_state_dict\x27})"'
]
res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
print("STDOUT:", res.stdout.decode('utf-8', errors='ignore'))
print("STDERR:", res.stderr.decode('utf-8', errors='ignore'))
