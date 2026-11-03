from pathlib import Path

fpath = Path("src/kalshi_sim/ml/wave_classifier.py")
text = fpath.read_text(encoding="utf-8")

target = '    def transition_to_healing(self, reason: str = "Initiating healing convalescence") -> None:'
replacement = '''    def reset(self, reason: str = "Manual reset to healthy STORM region") -> None:
        """Resets loss streaks, clears bleed state, and restores bot to healthy STORM operations."""
        self.current_region = "STORM"
        self.consecutive_losses = 0
        self.healing_consecutive_wins = 0
        self.last_transition_reason = reason
        logger.info("[WAVE CLASSIFIER] Region reset: %s", reason)

    def transition_to_healing(self, reason: str = "Initiating healing convalescence") -> None:'''

if target in text:
    text = text.replace(target, replacement, 1)
    fpath.write_text(text, encoding="utf-8")
    print("SUCCESS: Patched WaveRegimeClassifier.reset")
else:
    print("Target not found in wave_classifier.py")
