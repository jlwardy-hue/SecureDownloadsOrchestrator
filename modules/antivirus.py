import subprocess
import os
import logging
import hashlib
import time
import shutil

# EICAR test virus signature - safe test string used by antivirus software
EICAR_SIGNATURE = "X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"

def is_eicar_file(filepath):
    """
    Check if file contains EICAR test virus signature.
    
    Args:
        filepath: Path to the file to check
        
    Returns:
        bool: True if file contains EICAR signature
    """
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read(1024)  # Only read first 1KB for efficiency
            return EICAR_SIGNATURE in content
    except Exception:
        return False

def calculate_file_hash(filepath):
    """
    Calculate SHA256 hash of a file for malware detection.
    
    Args:
        filepath: Path to the file
        
    Returns:
        str: SHA256 hash or None if error
    """
    try:
        hasher = hashlib.sha256()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return None

def scan_file(filepath, config):
    """
    Enhanced antivirus scanning with EICAR support and robust error handling.
    
    Args:
        filepath: Path to the file to scan
        config: Configuration dictionary
        
    Returns:
        str: "clean", "quarantined", or "error"
    """
    logger = logging.getLogger("Orchestrator.Antivirus")
    
    # Validate file exists and is accessible
    if not os.path.exists(filepath):
        logger.warning(f"File does not exist for scanning: {filepath}")
        return "error"
        
    if not os.access(filepath, os.R_OK):
        logger.error(f"No read permission for file: {filepath}")
        return "error"
    
    # Get file information for logging
    try:
        file_size = os.path.getsize(filepath)
        file_hash = calculate_file_hash(filepath)
        logger.debug(f"Scanning file - Size: {file_size} bytes, Hash: {file_hash[:16] if file_hash else 'unknown'}...")
    except OSError as e:
        logger.warning(f"Could not get file information: {e}")
        file_size = 0
        file_hash = None
    
    # Check for EICAR test file first
    if is_eicar_file(filepath):
        logger.warning(f"EICAR test virus detected in: {filepath}")
        quarantine_dir = config['directories']['quarantine']
        os.makedirs(quarantine_dir, exist_ok=True)
        
        try:
            quarantine_path = os.path.join(quarantine_dir, f"EICAR_{int(time.time())}_{os.path.basename(filepath)}")
            shutil.move(filepath, quarantine_path)
            logger.info(f"EICAR file quarantined: {filepath} -> {quarantine_path}")
            return "quarantined"
        except Exception as e:
            logger.error(f"Failed to quarantine EICAR file: {e}")
            return "error"
    
    # ClamAV scanning
    clamscan = config['virus_scanning']['clamscan_path']
    quarantine = config['directories']['quarantine']
    
    try:
        os.makedirs(quarantine, mode=0o755, exist_ok=True)
    except OSError as e:
        logger.error(f"Failed to create quarantine directory: {e}")
        return "error"
    
    # Handle mock scanning for testing
    if clamscan == "echo":
        logger.info(f"Mock ClamAV scan for: {filepath} - Status: CLEAN")
        # Simulate some scanning time for realism
        time.sleep(0.1)
        return "clean"
    
    # Skip scanning for very large files to prevent timeouts
    max_scan_size = config.get('max_scan_size', 500 * 1024 * 1024)  # 500MB default
    if file_size > max_scan_size:
        logger.warning(f"File too large for scanning ({file_size} bytes > {max_scan_size}): {filepath}")
        logger.info(f"Large file bypass - assuming clean: {filepath}")
        return "clean"
    
    scan_timeout = config.get('scan_timeout', 300)  # 5 minutes default
    
    try:
        logger.debug(f"Starting ClamAV scan with timeout {scan_timeout}s: {filepath}")
        
        # Use --no-summary to reduce output and --move to quarantine infected files
        cmd = [clamscan, "--no-summary", "--move", quarantine, filepath]
        
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=scan_timeout,
            check=False  # Don't raise exception on non-zero exit codes
        )
        
        logger.debug(f"ClamAV exit code: {result.returncode}")
        if result.stdout.strip():
            logger.debug(f"ClamAV stdout: {result.stdout.strip()}")
        if result.stderr.strip():
            logger.debug(f"ClamAV stderr: {result.stderr.strip()}")
        
        # Check if file was moved to quarantine
        quarantined_path = os.path.join(quarantine, os.path.basename(filepath))
        if os.path.exists(quarantined_path):
            logger.warning(f"File quarantined by ClamAV: {filepath}")
            return "quarantined"
        
        # ClamAV return codes:
        # 0 = no virus found
        # 1 = virus found and cleaned/quarantined
        # 2 = some error occurred
        if result.returncode == 0:
            logger.debug(f"ClamAV scan clean: {filepath}")
            return "clean"
        elif result.returncode == 1:
            # Virus found but check if file was actually quarantined
            if not os.path.exists(filepath):
                logger.warning(f"File removed by ClamAV (infected): {filepath}")
                return "quarantined"
            else:
                logger.warning(f"ClamAV reported virus but file not quarantined: {filepath}")
                return "error"
        else:
            logger.error(f"ClamAV scan error (code {result.returncode}): {result.stderr}")
            return "error"
            
    except subprocess.TimeoutExpired:
        logger.error(f"ClamAV scan timed out after {scan_timeout}s: {filepath}")
        return "error"
    except subprocess.CalledProcessError as e:
        logger.error(f"ClamAV scan failed for {filepath}: {e}")
        return "error"
    except FileNotFoundError:
        logger.error(f"ClamAV not found at path: {clamscan}")
        logger.info("Install ClamAV or set clamscan_path to 'echo' for testing")
        return "error"
    except Exception as e:
        logger.error(f"Unexpected error during antivirus scan: {e}")
        return "error"
    
    # Optional: VirusTotal integration (future enhancement)
    vt_key = config['virus_scanning'].get('virustotal_api_key')
    if vt_key and file_hash:
        logger.debug(f"VirusTotal integration available but not implemented")
        # TODO: Implement VirusTotal API scanning
        # This would involve uploading file hash to VT API and checking results
    
    return "clean"
