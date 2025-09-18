import os
import logging
from datetime import datetime
import pandas as pd

def extract_metadata(filepath, config):
    logger = logging.getLogger("Orchestrator.Metadata")
    ext = os.path.splitext(filepath)[1].lower()
    metadata = {
        "filename": os.path.basename(filepath),
        "path": filepath,
        "size": os.path.getsize(filepath),
        "modified": datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat(),
        "created": datetime.fromtimestamp(os.path.getctime(filepath)).isoformat(),
    }
    # Extend here: add docx/pdf/image/ocr/etc extraction as needed

    # Save CSV index
    csv_path = os.path.join(config['directories']['organized'], "index.csv")
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
        df = pd.concat([df, pd.DataFrame([metadata])], ignore_index=True)
    else:
        df = pd.DataFrame([metadata])
    df.to_csv(csv_path, index=False)
    logger.info(f"Metadata indexed for {filepath}")
