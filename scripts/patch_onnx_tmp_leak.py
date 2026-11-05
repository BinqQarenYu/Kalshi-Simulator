with open('src/kalshi_sim/ml/onnx_engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_load_model = """        try:
            # Copy to temp directory to avoid Windows file lock issues with .onnx.data
            tmp_dir = tempfile.mkdtemp()
            active_onnx = os.path.join(tmp_dir, self.model_path.name)
            shutil.copy(self.model_path, active_onnx)

            data_file = str(self.model_path) + ".data"
            if os.path.exists(data_file):
                shutil.copy(data_file, active_onnx + ".data")

            self.session = ort.InferenceSession(
                active_onnx,
                sess_options=opts,
                providers=["CPUExecutionProvider"],
            )
            self.last_mtime = self.model_path.stat().st_mtime
            logger.info("[KalshiONNX] ONNX model '%s' successfully initialized in memory.", self.model_path.name)
        except Exception as exc:
            logger.error("[KalshiONNX] Failed to load ONNX model: %s", exc, exc_info=True)"""

new_load_model = """        try:
            old_tmp_dir = getattr(self, "_active_tmp_dir", None)
            
            # On Linux/AWS EC2, load directly from model_path without creating disk-exhausting temp directories.
            # On Windows only, use temp directory to avoid OS file-locking during background reloads.
            if sys.platform == "win32":
                tmp_dir = tempfile.mkdtemp()
                active_onnx = os.path.join(tmp_dir, self.model_path.name)
                shutil.copy(self.model_path, active_onnx)

                data_file = str(self.model_path) + ".data"
                if os.path.exists(data_file):
                    shutil.copy(data_file, active_onnx + ".data")
                self._active_tmp_dir = tmp_dir
            else:
                active_onnx = str(self.model_path)
                self._active_tmp_dir = None

            self.session = ort.InferenceSession(
                active_onnx,
                sess_options=opts,
                providers=["CPUExecutionProvider"],
            )
            self.last_mtime = self.model_path.stat().st_mtime

            # Safely clean up previous temporary directory to prevent /tmp disk bloat
            if old_tmp_dir and os.path.exists(old_tmp_dir):
                shutil.rmtree(old_tmp_dir, ignore_errors=True)

            logger.info("[KalshiONNX] ONNX model '%s' successfully initialized in memory.", self.model_path.name)
        except Exception as exc:
            logger.error("[KalshiONNX] Failed to load ONNX model: %s", exc, exc_info=True)"""

if old_load_model in content:
    content = content.replace(old_load_model, new_load_model, 1)
    with open('src/kalshi_sim/ml/onnx_engine.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("SUCCESS: Patched onnx_engine.py to prevent /tmp leak")
else:
    print("FAILED: old_load_model block not found")
