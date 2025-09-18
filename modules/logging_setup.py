import logging
import os

def setup_logging(log_path, level="INFO"):
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_path),
            logging.StreamHandler()
        ]
    )
