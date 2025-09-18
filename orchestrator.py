import logging
import os
import yaml
import time
import traceback
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
IGNORE_EXTENSIONS = [".part", ".crdownload", ".tmp", ".temp", ".downloading"]

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY_BASE = 1  # Base delay in seconds
RETRY_BACKOFF_MULTIPLIER = 2

def retry_operation(operation, *args, **kwargs):
    """
    Retry an operation with exponential backoff.
    
    Args:
        operation: Function to execute
        *args: Arguments for the operation
        **kwargs: Keyword arguments for the operation
        
    Returns:
        Result of the operation or None if all retries failed
    """
    for attempt in range(MAX_RETRIES):
        try:
            logger.debug(f"Attempting operation {operation.__name__} (attempt {attempt + 1}/{MAX_RETRIES})")
            result = operation(*args, **kwargs)
            if attempt > 0:
                logger.info(f"Operation {operation.__name__} succeeded on attempt {attempt + 1}")
            return result
        except Exception as e:
            delay = RETRY_DELAY_BASE * (RETRY_BACKOFF_MULTIPLIER ** attempt)
            logger.warning(f"Operation {operation.__name__} failed on attempt {attempt + 1}: {e}")
            
            if attempt < MAX_RETRIES - 1:
                logger.info(f"Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                logger.error(f"Operation {operation.__name__} failed after {MAX_RETRIES} attempts")
                logger.debug(f"Final error details: {traceback.format_exc()}")
                
    return None

def safe_file_operation(filepath, operation_name, operation_func, *args, **kwargs):
    """
    Safely perform file operations with validation and retry logic.
    
    Args:
        filepath: Path to the file
        operation_name: Name of the operation for logging
        operation_func: Function to execute
        *args: Arguments for the operation
        **kwargs: Keyword arguments for the operation
        
    Returns:
        Result of the operation or None if failed
    """
    logger.debug(f"Starting {operation_name} for: {filepath}")
    
    # Pre-operation validation
    if not os.path.exists(filepath):
        logger.warning(f"File no longer exists for {operation_name}: {filepath}")
        return None
        
    # Check file permissions
    if not os.access(filepath, os.R_OK):
        logger.error(f"No read permission for {operation_name}: {filepath}")
        return None
        
    # Get file stats for logging
    try:
        stat_info = os.stat(filepath)
        logger.debug(f"File stats - Size: {stat_info.st_size} bytes, Mode: {oct(stat_info.st_mode)}")
    except OSError as e:
        logger.warning(f"Could not get file stats for {filepath}: {e}")
    
    # Execute operation with retry
    result = retry_operation(operation_func, filepath, *args, **kwargs)
    
    if result is not None:
        logger.debug(f"Successfully completed {operation_name} for: {filepath}")
    else:
        logger.error(f"Failed to complete {operation_name} after all retries for: {filepath}")
        
    return result
def process_new_file(filepath, retry_count=0):
    """
    Process a new file through the complete pipeline with enhanced error handling.
    
    Args:
        filepath: Path to the file to process
        retry_count: Current retry attempt (for recursive calls)
    """
    logger.info(f"Processing new file: {filepath} (attempt {retry_count + 1})")
    
    # Check if file exists first
    if not os.path.exists(filepath):
        logger.warning(f"File no longer exists, skipping: {filepath}")
        return

    # Enhanced file validation
    try:
        file_size = os.path.getsize(filepath)
        file_ext = os.path.splitext(filepath)[1].lower()
        base_name = os.path.basename(filepath)
        
        # Check for special characters that might cause issues
        problematic_chars = ['<', '>', ':', '"', '|', '?', '*']
        if any(char in base_name for char in problematic_chars):
            logger.warning(f"File contains problematic characters: {filepath}")
            # Sanitize filename if needed
        
        logger.debug(f"File details - Name: {base_name}, Size: {file_size} bytes, Extension: {file_ext}")
        
        # Check for extremely large files
        if file_size > 10 * 1024 * 1024 * 1024:  # 10GB
            logger.warning(f"Very large file detected ({file_size} bytes): {filepath}")
            
        # Check for zero-byte files
        if file_size == 0:
            logger.warning(f"Zero-byte file detected: {filepath}")
            
    except OSError as e:
        logger.error(f"Error getting file info for {filepath}: {e}")
        return

    # Ignore incomplete/temp files with expanded list
    if any(filepath.lower().endswith(ext) for ext in IGNORE_EXTENSIONS):
        logger.info(f"Ignored incomplete/temp file: {filepath}")
        return

    # Step 1: Virus scan with retry logic
    logger.debug(f"Starting virus scan for: {filepath}")
    scan_result = safe_file_operation(filepath, "virus scan", scan_file, config)
    
    if scan_result == "quarantined":
        logger.warning(f"File {filepath} quarantined by antivirus.")
        return
    elif scan_result == "error":
        logger.error(f"Virus scan failed for {filepath}")
        if retry_count < MAX_RETRIES - 1:
            logger.info(f"Retrying file processing for {filepath}")
            time.sleep(RETRY_DELAY_BASE * (RETRY_BACKOFF_MULTIPLIER ** retry_count))
            process_new_file(filepath, retry_count + 1)
        return
    elif scan_result is None:
        logger.error(f"Virus scan returned None for {filepath}")
        return
        
    logger.debug(f"Virus scan passed for: {filepath}")

    # Step 2: Extract if archive with enhanced error handling
    if any(filepath.lower().endswith(ext) for ext in config['archive_extensions']):
        logger.info(f"Identified as archive file: {filepath}")
        
        extracted_files = safe_file_operation(filepath, "archive extraction", extract_archives, config)
        
        if extracted_files is not None:
            logger.info(f"Extracted {len(extracted_files)} files from archive: {filepath}")
            
            # Process extracted files with depth tracking to prevent infinite recursion
            max_extraction_depth = config.get('max_extraction_depth', 5)
            current_depth = getattr(process_new_file, '_extraction_depth', 0)
            
            if current_depth >= max_extraction_depth:
                logger.warning(f"Maximum extraction depth ({max_extraction_depth}) reached, skipping nested extraction")
                return
                
            process_new_file._extraction_depth = current_depth + 1
            
            try:
                for extracted in extracted_files:
                    logger.debug(f"Processing extracted file: {extracted}")
                    if os.path.exists(extracted):  # Double-check existence
                        process_new_file(extracted, 0)  # Reset retry count for extracted files
                    else:
                        logger.warning(f"Extracted file no longer exists: {extracted}")
            finally:
                process_new_file._extraction_depth = current_depth
        else:
            logger.error(f"Archive extraction failed for {filepath}")
            
        return

    # Step 3: Organize and deduplicate with retry logic
    logger.debug(f"Starting file organization for: {filepath}")
    organized_path = safe_file_operation(filepath, "file organization", organize_file, config)
    
    if organized_path is None:
        logger.error(f"File organization failed for {filepath}")
        if retry_count < MAX_RETRIES - 1:
            logger.info(f"Retrying file processing for {filepath}")
            time.sleep(RETRY_DELAY_BASE * (RETRY_BACKOFF_MULTIPLIER ** retry_count))
            process_new_file(filepath, retry_count + 1)
        return

    # Step 4: Metadata extraction with error handling
    logger.debug(f"Starting metadata extraction for: {organized_path}")
    metadata_result = safe_file_operation(organized_path, "metadata extraction", extract_metadata, config)
    
    if metadata_result is not None:
        logger.info(f"Successfully completed processing: {os.path.basename(filepath)} -> {organized_path}")
    else:
        logger.warning(f"Metadata extraction failed but file was organized: {organized_path}")
        # Don't retry for metadata failures as the file is already organized

def process_existing_files(watch_dir):
    """
    Enhanced processing of existing files in the watch directory.
    
    Args:
        watch_dir: Directory to scan for existing files
    """
    logger.info(f"Scanning for existing files in {watch_dir}...")
    
    # Check if watch directory exists
    if not os.path.exists(watch_dir):
        logger.error(f"Watch directory does not exist: {watch_dir}")
        logger.info("Please create the watch directory or update config.yaml")
        return
        
    # Check directory permissions
    if not os.access(watch_dir, os.R_OK):
        logger.error(f"No read permission for watch directory: {watch_dir}")
        return
        
    try:
        files = os.listdir(watch_dir)
        logger.info(f"Found {len(files)} items in watch directory")
        
        file_count = 0
        processed_count = 0
        error_count = 0
        
        # Sort files to ensure consistent processing order
        files.sort()
        
        for fname in files:
            fpath = os.path.join(watch_dir, fname)
            
            try:
                if os.path.isfile(fpath):
                    file_count += 1
                    logger.debug(f"Processing existing file: {fname}")
                    
                    # Check for problematic filenames early
                    if len(fname) > 255:
                        logger.warning(f"Filename too long, skipping: {fname[:50]}...")
                        continue
                    
                    # Skip hidden files and system files unless explicitly configured
                    if fname.startswith('.') and not config.get('process_hidden_files', False):
                        logger.debug(f"Skipping hidden file: {fname}")
                        continue
                    
                    # Process the file
                    process_new_file(fpath, 0)  # Start with retry count 0
                    processed_count += 1
                    
                elif os.path.isdir(fpath):
                    logger.debug(f"Skipping subdirectory: {fname}")
                else:
                    logger.debug(f"Skipping non-regular file: {fname}")
                    
            except Exception as e:
                error_count += 1
                logger.error(f"Error processing existing file {fname}: {e}")
                logger.debug(f"Error details: {traceback.format_exc()}")
                
        logger.info(f"Existing file processing complete - Found: {file_count}, Processed: {processed_count}, Errors: {error_count}")
        
        if error_count > 0:
            logger.warning(f"{error_count} files failed processing. Check DEBUG logs for details.")
        
    except PermissionError:
        logger.error(f"Permission denied accessing watch directory: {watch_dir}")
    except OSError as e:
        logger.error(f"OS error scanning watch directory {watch_dir}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error scanning watch directory {watch_dir}: {e}")
        logger.debug(f"Error details: {traceback.format_exc()}")

def main():
    logger.info("SecureDownloads Orchestrator started.")
    process_existing_files(config['directories']['watch'])
    monitor = FolderMonitor(config['directories']['watch'], process_new_file)
    monitor.start()

if __name__ == "__main__":
    main()
