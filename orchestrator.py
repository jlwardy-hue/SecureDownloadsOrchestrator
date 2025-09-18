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
    logger.info(f"Processing new file: {filepath}")
    
    # Check if file exists first
    if not os.path.exists(filepath):
        logger.warning(f"File no longer exists, skipping: {filepath}")
        return

    # Get file info for logging
    file_size = os.path.getsize(filepath)
    file_ext = os.path.splitext(filepath)[1].lower()
    logger.debug(f"File details - Size: {file_size} bytes, Extension: {file_ext}")

    # Ignore incomplete/temp files
    if any(filepath.lower().endswith(ext) for ext in IGNORE_EXTENSIONS):
        logger.info(f"Ignored incomplete/temp file: {filepath}")
        return

    # Step 1: Virus scan
    logger.debug(f"Starting virus scan for: {filepath}")
    scan_result = scan_file(filepath, config)
    if scan_result == "quarantined":
        logger.warning(f"File {filepath} quarantined by antivirus.")
        return
    logger.debug(f"Virus scan passed for: {filepath}")

    # Step 2: Extract if archive
    if any(filepath.lower().endswith(ext) for ext in config['archive_extensions']):
        logger.info(f"Identified as archive file: {filepath}")
        try:
            extracted_files = extract_archives(filepath, config)
            logger.info(f"Extracted {len(extracted_files)} files from archive: {filepath}")
            for extracted in extracted_files:
                logger.debug(f"Processing extracted file: {extracted}")
                process_new_file(extracted)
        except Exception as e:
            logger.error(f"Error extracting archive {filepath}: {e}")
        return

    # Step 3: Organize and deduplicate
    logger.debug(f"Starting file organization for: {filepath}")
    try:
        organized_path = organize_file(filepath, config)
        if not organized_path:
            logger.warning(f"File organization returned no path for: {filepath}")
            return
    except Exception as e:
        logger.error(f"Error organizing file {filepath}: {e}")
        return

    # Step 4: Metadata extraction
    logger.debug(f"Starting metadata extraction for: {organized_path}")
    try:
        extract_metadata(organized_path, config)
        logger.info(f"Successfully completed processing: {os.path.basename(filepath)} -> {organized_path}")
    except Exception as e:
        logger.error(f"Error extracting metadata from {organized_path}: {e}")

def process_existing_files(watch_dir):
    logger.info(f"Scanning for existing files in {watch_dir}...")
    
    # Check if watch directory exists
    if not os.path.exists(watch_dir):
        logger.error(f"Watch directory does not exist: {watch_dir}")
        logger.info("Please create the watch directory or update config.yaml")
        return
        
    try:
        files = os.listdir(watch_dir)
        logger.info(f"Found {len(files)} items in watch directory")
        
        file_count = 0
        for fname in files:
            fpath = os.path.join(watch_dir, fname)
            if os.path.isfile(fpath):
                file_count += 1
                logger.debug(f"Processing existing file: {fname}")
                process_new_file(fpath)
                
        logger.info(f"Processed {file_count} existing files")
        
    except PermissionError:
        logger.error(f"Permission denied accessing watch directory: {watch_dir}")
    except Exception as e:
        logger.error(f"Error scanning watch directory {watch_dir}: {e}")

def main():
    logger.info("SecureDownloads Orchestrator started.")
    process_existing_files(config['directories']['watch'])
    monitor = FolderMonitor(config['directories']['watch'], process_new_file)
    monitor.start()

if __name__ == "__main__":
    main()
