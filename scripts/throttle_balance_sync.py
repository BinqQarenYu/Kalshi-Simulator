from pathlib import Path

fpath = Path("src/kalshi_sim/server.py")
text = fpath.read_text(encoding="utf-8")

old_code = """            except Exception as exc:
                logger.debug("Live balance sync loop iteration exception: %s", exc)
            await asyncio.sleep(5.0)"""

new_code = """            except Exception as exc:
                logger.debug("Live balance sync loop iteration exception: %s", exc)
            await asyncio.sleep(20.0)"""

if old_code in text:
    text = text.replace(old_code, new_code, 1)
    fpath.write_text(text, encoding="utf-8")
    print("SUCCESS: Throttled live balance sync loop to 20.0s to eliminate HTTP 429")
else:
    print("WARNING: Target code not found in server.py")
