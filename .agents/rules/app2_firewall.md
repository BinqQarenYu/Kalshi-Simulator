# Rule: App 2 (Execution Bot) Strict Firewall
# Role: Low-Latency Execution Engine

1. **Isolation**: Any agent assigned to pp_2_execution_bot is STRICTLY FORBIDDEN from reading, writing, or traversing into pp_1_machine_engine or pp_3_autonomous_chef.
2. **Execution Contract**: App 2 must load the .onnx model locally from disk via onnxruntime. It is forbidden from making HTTP calls to an inference server. It must contain zero heavy ML training libraries (no PyTorch, no TensorFlow).
3. **Failure Condition**: Any attempt to import ML training code from App 1 or modify App 1/3 files is a strict failure condition.
