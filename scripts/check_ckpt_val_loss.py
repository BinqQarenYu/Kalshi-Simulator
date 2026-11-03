import subprocess

cmd = [
    'ssh', '-i', 'kalshi_aws_key.pem',
    '-o', 'StrictHostKeyChecking=no',
    '-o', 'ConnectTimeout=10',
    'ec2-user@13.63.158.94',
    'cd /home/ec2-user/kalshi-bot && source venv/bin/activate && python -c "import torch; ckpt = torch.load(\'models/best_model.pt\', map_location=\'cpu\'); print(\'keys:\', list(ckpt.keys()) if isinstance(ckpt, dict) else type(ckpt)); print(\'val_loss:\', ckpt.get(\'val_loss\') if isinstance(ckpt, dict) else None)"'
]
res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
print("STDOUT:", res.stdout)
print("STDERR:", res.stderr)
