import os
import shutil
import zipfile
import tarfile
import subprocess
import logging
import tempfile
import stat
import time
from pathlib import Path

def run_command(cmd, cwd, timeout=300):
    """
    Run a command with enhanced error handling and timeout.
    
    Args:
        cmd: Command to run
        cwd: Working directory
        timeout: Command timeout in seconds
        
    Returns:
        tuple: (success, output/error)
    """
    logger = logging.getLogger("Orchestrator.Extract")
    try:
        logger.debug(f"Running command: {' '.join(cmd)} in {cwd}")
        result = subprocess.run(
            cmd, 
            cwd=cwd, 
            check=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True,
            timeout=timeout
        )
        return True, result.stdout
    except subprocess.TimeoutExpired as e:
        logger.error(f"Command timed out after {timeout}s: {' '.join(cmd)}")
        return False, f"Command timed out: {e}"
    except subprocess.CalledProcessError as e:
        logger.debug(f"Command failed with return code {e.returncode}: {e.stderr}")
        return False, e.stderr
    except Exception as e:
        logger.error(f"Unexpected error running command: {e}")
        return False, str(e)

def safe_extract_path(extract_to, member_path):
    """
    Safely construct extraction path to prevent directory traversal attacks.
    
    Args:
        extract_to: Base extraction directory
        member_path: Path of the member being extracted
        
    Returns:
        str: Safe extraction path or None if unsafe
    """
    # Normalize paths and resolve any .. components
    extract_to = os.path.abspath(extract_to)
    member_path = os.path.normpath(member_path)
    
    # Remove leading slash or drive letters to make path relative
    if os.path.isabs(member_path):
        member_path = member_path.lstrip(os.sep)
        if os.name == 'nt' and ':' in member_path:
            member_path = member_path.split(':', 1)[1].lstrip(os.sep)
    
    # Construct the full path
    full_path = os.path.join(extract_to, member_path)
    full_path = os.path.abspath(full_path)
    
    # Ensure the path is within the extraction directory
    if not full_path.startswith(extract_to + os.sep) and full_path != extract_to:
        return None
        
    return full_path

def clean_extraction_directory(extract_to, logger):
    """
    Safely clean the extraction directory with enhanced error handling.
    
    Args:
        extract_to: Directory to clean
        logger: Logger instance
    """
    if not os.path.exists(extract_to):
        return
        
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            for item in os.listdir(extract_to):
                item_path = os.path.join(extract_to, item)
                try:
                    if os.path.isfile(item_path) or os.path.islink(item_path):
                        # Handle read-only files
                        if not os.access(item_path, os.W_OK):
                            os.chmod(item_path, stat.S_IWRITE | stat.S_IREAD)
                        os.unlink(item_path)
                    elif os.path.isdir(item_path):
                        # Handle read-only directories
                        for root, dirs, files in os.walk(item_path):
                            for d in dirs:
                                os.chmod(os.path.join(root, d), stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
                            for f in files:
                                file_path = os.path.join(root, f)
                                os.chmod(file_path, stat.S_IWRITE | stat.S_IREAD)
                        shutil.rmtree(item_path)
                except PermissionError as e:
                    logger.warning(f"Permission denied cleaning {item_path}: {e}")
                    if attempt == max_attempts - 1:
                        logger.error(f"Failed to clean {item_path} after {max_attempts} attempts")
                except Exception as e:
                    logger.warning(f"Error cleaning {item_path}: {e}")
            break
        except Exception as e:
            if attempt < max_attempts - 1:
                logger.debug(f"Cleanup attempt {attempt + 1} failed, retrying: {e}")
                time.sleep(0.5)
            else:
                logger.warning(f"Failed to clean extraction directory after {max_attempts} attempts: {e}")

def extract_archives(filepath, config):
    """
    Enhanced archive extraction with security checks and error handling.
    
    Args:
        filepath: Path to the archive file
        config: Configuration dictionary
        
    Returns:
        list: List of extracted file paths
    """
    logger = logging.getLogger("Orchestrator.Extract")
    tmp_unzip = config['directories']['tmp_unzip']
    
    # Create extraction directory with proper permissions
    try:
        os.makedirs(tmp_unzip, mode=0o755, exist_ok=True)
    except OSError as e:
        logger.error(f"Failed to create extraction directory {tmp_unzip}: {e}")
        return []
    
    extracted_files = []
    file_path = Path(filepath)
    ext = file_path.suffix.lower()
    
    # Handle compound extensions like .tar.gz
    if file_path.suffixes:
        compound_ext = ''.join(file_path.suffixes).lower()
        if compound_ext in ['.tar.gz', '.tar.bz2', '.tar.xz']:
            ext = compound_ext
    
    # Create a unique extraction subdirectory to avoid conflicts
    extract_to = os.path.join(tmp_unzip, f"extract_{int(time.time())}_{os.getpid()}")
    
    try:
        os.makedirs(extract_to, mode=0o755)
        logger.debug(f"Created extraction directory: {extract_to}")
    except OSError as e:
        logger.error(f"Failed to create unique extraction directory: {e}")
        return []

    # Clean any previous extractions
    clean_extraction_directory(extract_to, logger)
    
    # Set extraction limits to prevent zip bombs
    max_files = config.get('max_extraction_files', 10000)
    max_size = config.get('max_extraction_size', 10 * 1024 * 1024 * 1024)  # 10GB
    max_compression_ratio = config.get('max_compression_ratio', 100)
    
    try:
        files_extracted = 0
        total_size = 0
        archive_size = os.path.getsize(filepath)
        
        if ext == ".zip":
            logger.debug(f"Extracting ZIP archive: {filepath}")
            with zipfile.ZipFile(filepath, 'r') as zf:
                # Check for zip bomb indicators
                for info in zf.infolist():
                    if files_extracted >= max_files:
                        logger.warning(f"Extraction stopped: too many files (>{max_files})")
                        break
                        
                    if total_size + info.file_size > max_size:
                        logger.warning(f"Extraction stopped: total size would exceed {max_size} bytes")
                        break
                        
                    # Check compression ratio
                    if info.compress_size > 0:
                        ratio = info.file_size / info.compress_size
                        if ratio > max_compression_ratio:
                            logger.warning(f"Suspicious compression ratio ({ratio:.1f}) for {info.filename}")
                            continue
                    
                    # Check for directory traversal
                    safe_path = safe_extract_path(extract_to, info.filename)
                    if safe_path is None:
                        logger.warning(f"Skipping potentially malicious path: {info.filename}")
                        continue
                    
                    # Extract the file
                    try:
                        zf.extract(info, extract_to)
                        files_extracted += 1
                        total_size += info.file_size
                        logger.debug(f"Extracted: {info.filename} ({info.file_size} bytes)")
                    except Exception as e:
                        logger.warning(f"Failed to extract {info.filename}: {e}")
                        
            logger.info(f"Extracted ZIP: {filepath} ({files_extracted} files, {total_size} bytes)")
            
        elif ext in [".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar", ".tar.xz"]:
            logger.debug(f"Extracting TAR archive: {filepath}")
            with tarfile.open(filepath, 'r:*') as tf:
                for member in tf:
                    if files_extracted >= max_files:
                        logger.warning(f"Extraction stopped: too many files (>{max_files})")
                        break
                        
                    if total_size + member.size > max_size:
                        logger.warning(f"Extraction stopped: total size would exceed {max_size} bytes")
                        break
                    
                    # Check for directory traversal
                    safe_path = safe_extract_path(extract_to, member.name)
                    if safe_path is None:
                        logger.warning(f"Skipping potentially malicious path: {member.name}")
                        continue
                    
                    # Extract the member
                    try:
                        tf.extract(member, extract_to)
                        files_extracted += 1
                        total_size += member.size
                        logger.debug(f"Extracted: {member.name} ({member.size} bytes)")
                    except Exception as e:
                        logger.warning(f"Failed to extract {member.name}: {e}")
                        
            logger.info(f"Extracted TAR: {filepath} ({files_extracted} files, {total_size} bytes)")
            
        elif ext == ".rar" and shutil.which("unrar"):
            logger.debug(f"Extracting RAR archive: {filepath}")
            cmd = ["unrar", "x", "-o+", "-y", filepath, extract_to + os.sep]
            success, output = run_command(cmd, cwd=os.path.dirname(filepath))
            if success:
                logger.info(f"Extracted RAR: {filepath}")
                # Count extracted files
                for root, dirs, files in os.walk(extract_to):
                    files_extracted += len(files)
            else:
                logger.warning(f"RAR extraction failed: {filepath} - {output}")
                return []
                
        elif ext == ".7z" and shutil.which("7z"):
            logger.debug(f"Extracting 7z archive: {filepath}")
            cmd = ["7z", "x", f"-o{extract_to}", "-y", filepath]
            success, output = run_command(cmd, cwd=os.path.dirname(filepath))
            if success:
                logger.info(f"Extracted 7z: {filepath}")
                # Count extracted files
                for root, dirs, files in os.walk(extract_to):
                    files_extracted += len(files)
            else:
                logger.warning(f"7z extraction failed: {filepath} - {output}")
                return []
        else:
            logger.warning(f"Unsupported archive type: {ext} for file {filepath}")
            return []
            
    except zipfile.BadZipFile as e:
        logger.error(f"Corrupted ZIP file: {filepath} - {e}")
        return []
    except tarfile.TarError as e:
        logger.error(f"Corrupted TAR file: {filepath} - {e}")
        return []
    except Exception as e:
        logger.error(f"Extraction failed for {filepath}: {e}")
        return []

    # List all extracted files with validation
    logger.debug(f"Scanning extracted files in: {extract_to}")
    try:
        for root, dirs, files in os.walk(extract_to):
            for f in files:
                file_path = os.path.join(root, f)
                if os.path.exists(file_path) and os.path.isfile(file_path):
                    extracted_files.append(file_path)
                    logger.debug(f"Found extracted file: {file_path}")
                else:
                    logger.warning(f"Extracted file missing or invalid: {file_path}")
                    
        logger.info(f"Successfully extracted {len(extracted_files)} files from {filepath}")
        
    except Exception as e:
        logger.error(f"Error scanning extracted files: {e}")
        
    return extracted_files
