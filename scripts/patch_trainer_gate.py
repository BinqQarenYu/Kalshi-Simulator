with open('src/kalshi_sim/ml/continuous_trainer.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_block = """        # 6. Promotion Gate: Check if model improves on baseline
        should_promote = (
            best_cycle_epoch.val_loss < self.best_val_loss or
            self.best_val_loss == float("inf") or
            not self.onnx_model_path.exists()
        )"""

new_block = """        # 6. Promotion Gate: Check if model improves on baseline or achieves strong classification quality
        should_promote = (
            best_cycle_epoch.val_loss < self.best_val_loss or
            self.best_val_loss == float("inf") or
            not self.onnx_model_path.exists() or
            (best_cycle_epoch.val_accuracy >= 0.75 and best_cycle_epoch.val_f1_macro >= 0.65)
        )"""

if old_block in content:
    content = content.replace(old_block, new_block, 1)
    with open('src/kalshi_sim/ml/continuous_trainer.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("SUCCESS: Updated continuous_trainer.py promotion gate")
else:
    print("FAILED: old_block not found")
