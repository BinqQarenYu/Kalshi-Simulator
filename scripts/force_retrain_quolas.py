
import sys
sys.path.insert(0, "src")
from pathlib import Path
from kalshi_sim.ml.dataset_builder import DatasetBuilder
from kalshi_sim.ml.model import QuoLasMicroscopeNet
from kalshi_sim.ml.train_model import ModelTrainer
from kalshi_sim.ml.continuous_trainer import export_and_verify_onnx
import torch

def main():
    print("Starting forceful robust retraining of quolas.onnx...")
    data_dir = Path("data")

    builder = DatasetBuilder(
        horizon_steps=15,
        horizon_seconds=20.0,
        price_diff_threshold=0.03,
        sample_stride=1,
        max_frames_per_file=50000, 
        max_wait_ratio=0.50,
    )
    
    print("Extracting features from historical tick file...")
    X, y = builder.build_from_directory(data_dir, file_pattern="ticks_paper_live_20260927_150911.jsonl", max_files=1)
    print(f"Extracted {len(X)} valid volatility samples.")
    
    if len(X) < 64:
        print("Not enough samples found. Aborting.")
        return
        
    model = QuoLasMicroscopeNet(input_dim=28, hidden_dim=64, num_classes=3)
    
    ckpt_path = Path("models/best_model.pt")
    if ckpt_path.exists():
        try:
            ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=True)
            if "model_state_dict" in ckpt:
                model.load_state_dict(ckpt["model_state_dict"])
                print("Loaded existing weights from best_model.pt for fine-tuning.")
        except Exception as e:
            print(f"Failed to load checkpoint: {e}")
            
    trainer = ModelTrainer(model, learning_rate=2e-4)
    print("Training model for 5 epochs...")
    metrics = trainer.fit(X, y, X, y, epochs=5, batch_size=64)
    
    print(f"Training complete. Checkpoint saved. Now exporting ONNX...")
    out_path = Path("models/quolas.onnx")
    success = export_and_verify_onnx(model, out_path)
    if success:
        print(f"Successfully exported and verified {out_path}!")
    else:
        print("Failed to export quolas.onnx!")
        
if __name__ == "__main__":
    main()

