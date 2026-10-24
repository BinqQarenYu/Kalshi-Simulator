import sys
sys.path.insert(0, '/home/ec2-user/kalshi-bot/src')
from datetime import datetime, timezone
from kalshi_sim.ml.session_timing_guard import get_session_timing_guard

g = get_session_timing_guard()
print(f"SessionTimingGuard: enabled={g.enabled}, strict_golden_only={g.strict_golden_only}")
for hour_utc in [6, 7, 8, 12, 15, 21, 22]:
    dt = datetime(2026, 10, 24, hour_utc, 15, tzinfo=timezone.utc)
    v = g.evaluate_timing(dt)
    dt_et = g.get_current_et_datetime(dt)
    print(f"UTC {hour_utc:02d}:15 -> ET {dt_et.hour:02d}:15 (Qatar {(hour_utc+3)%24:02d}:15) | Allowed: {v.allowed} | Golden: {v.is_golden} | Session: {v.session_name} | Reason: {v.reason[:70]}")
