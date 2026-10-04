import os
import time
import glob
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [SCRUBBER] %(message)s')

DATA_DIR = 'data'
MAX_AGE_DAYS = 2

def scrub():
    files = glob.glob(os.path.join(DATA_DIR, 'ticks_paper_live_*.jsonl'))
    now = time.time()
    
    deleted_count = 0
    deleted_bytes = 0
    
    # Sort files by modification time so we don't delete the most recent active one
    files.sort(key=os.path.getmtime)
    
    # Leave the last (most recent) file alone since it's actively being written to
    active_file = files[-1] if files else None
    
    for f in files:
        if f == active_file:
            continue
            
        size = os.path.getsize(f)
        mtime = os.path.getmtime(f)
        age_days = (now - mtime) / (24 * 3600)
        
        # Rule 1: Delete 0-byte unwanted files
        # Rule 2: Delete raw data older than MAX_AGE_DAYS
        if size == 0 or age_days > MAX_AGE_DAYS:
            try:
                os.remove(f)
                deleted_count += 1
                deleted_bytes += size
                logging.info(f"Deleted unwanted raw data: {os.path.basename(f)} (Size: {size/(1024*1024):.2f} MB, Age: {age_days:.1f} days)")
            except Exception as e:
                logging.error(f"Failed to delete {f}: {e}")
                
    if deleted_count > 0:
        logging.info(f"Scrub cycle complete. Deleted {deleted_count} unwanted files saving {deleted_bytes/(1024*1024*1024):.2f} GB.")
        
if __name__ == '__main__':
    logging.info("Continuous Scrubber started. Only clean/active data will be retained.")
    while True:
        try:
            scrub()
        except Exception as e:
            logging.error(f"Scrubber error: {e}")
        # Run every 30 minutes
        time.sleep(1800)
