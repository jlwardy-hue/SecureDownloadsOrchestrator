import logging
import os
import yaml
from modules.logging_setup import setup_logging
from modules.monitor import FolderMonitor
from modules.antivirus import scan_file
from modules.extract import extract_archives
from modules.organize import organize_file
from modules.metadata import extract_metadata

# Load config
with open("config.yaml") as f:
    config = yaml.safe_load(f)

setup_logging(config['directories']['logs'], config.get('log_level', 'INFO'))
logger = logging.getLogger("Orchestrator")

# Extensions to ignore (incomplete downloads, temp files)
IGNORE_EXTENSIONS = [".part", ".crdownload", ".tmp"]

def process_new_file(filepath):
    logger.info(f"Detected file: {filepath}")

    # Ignore incomplete/temp files
    if any(filepath.lower().endswith(ext) for ext in IGNORE_EXTENSIONS):
        logger.info(f"Ignored incomplete/temp file: {filepath}")
        return

    # Step 1: Virus scan
    scan_result = scan_file(filepath, config)
    if scan_result == "quarantined":
        logger.warning(f"File {filepath} quarantined by antivirus.")
        return

    # Step 2: Extract if archive
    if any(filepath.lower().endswith(ext) for ext in config['archive_extensions']):
        try:
            extracted_files = extract_archives(filepath, config)
            for extracted in extracted_files:
                process_new_file(extracted)
        except Exception as e:
            logger.error(f"Error extracting archive {filepath}: {e}")
        return

    # Step 3: Organize and deduplicate
    try:
        organized_path = organize_file(filepath, config)
    except Exception as e:
        logger.error(f"Error organizing file {filepath}: {e}")
        return

    if organized_path:
        # Step 4: Metadata extraction
        try:
            extract_metadata(organized_path, config)
            logger.info(f"Completed processing: {organized_path}")
        except Exception as e:
            logger.error(f"Error extracting metadata from {organized_path}: {e}")

def process_existing_files(watch_dir):
    logger.info(f"Scanning for existing files in {watch_dir}...")
    for fname in os.listdir(watch_dir):
        fpath = os.path.join(watch_dir, fname)
        if os.path.isfile(fpath):
            process_new_file(fpath)

def main():
    logger.info("SecureDownloads Orchestrator started.")
    process_existing_files(config['directories']['watch'])
    monitor = FolderMonitor(config['directories']['watch'], process_new_file)
    monitor.start()

if __name__ == "__main__":
    main()
