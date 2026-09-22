# Rule: App 1 (Machine Engine) Strict Firewall
# Role: Quant Factory

1. **Isolation**: Any agent assigned to pp_1_machine_engine is STRICTLY FORBIDDEN from reading, writing, or traversing into pp_2_execution_bot or pp_3_autonomous_chef.
2. **Output Contract**: The ONLY allowed output is writing a serialized .onnx file to a local designated path (e.g., models/model.onnx). No network sockets or HTTP servers are allowed to serve this model.
3. **Failure Condition**: Any attempt to modify code in App 2 or App 3 by an App 1 agent is a fatal error and strict failure condition.
