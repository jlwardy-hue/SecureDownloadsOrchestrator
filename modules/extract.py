import os
import shutil
import zipfile
import tarfile
import subprocess
import logging
import tempfile
import io

def run_command(cmd, cwd):
    try:
        result = subprocess.run(cmd, cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr

def extract_archives(filepath, config):
    logger = logging.getLogger("Orchestrator.Extract")
    logger.debug("Archive extraction module initialized")
    
    # Use secure random temporary directory instead of predictable path
    extract_to = tempfile.mkdtemp(prefix="secure_extract_", suffix="_tmp")
    logger.debug(f"Created secure temporary directory: {extract_to}")
    
    extracted_files = []
    ext = os.path.splitext(filepath)[1].lower()

    # No need to clean since we're using a fresh secure temp directory
    # The directory cleanup will happen at the end of the function

    try:
        if ext == ".zip":
            with zipfile.ZipFile(filepath, 'r') as zf:
                zf.extractall(extract_to)
            logger.info(f"Extracted ZIP: {filepath}")
        elif any(filepath.endswith(x) for x in [".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar"]):
            with tarfile.open(filepath, 'r:*') as tf:
                tf.extractall(extract_to)
            logger.info(f"Extracted TAR: {filepath}")
        elif ext == ".rar" and shutil.which("unrar"):
            cmd = ["unrar", "x", "-o+", filepath, extract_to]
            success, output = run_command(cmd, cwd=os.path.dirname(filepath))
            if success:
                logger.info(f"Extracted RAR: {filepath}")
            else:
                logger.warning(f"RAR extraction failed: {filepath}")
        elif ext == ".7z" and shutil.which("7z"):
            cmd = ["7z", "x", filepath, f"-o{extract_to}", "-y"]
            success, output = run_command(cmd, cwd=os.path.dirname(filepath))
            if success:
                logger.info(f"Extracted 7z: {filepath}")
            else:
                logger.warning(f"7z extraction failed: {filepath}")
        else:
            logger.warning(f"Unsupported archive type for: {filepath}")
            return []
    except Exception as e:
        logger.error(f"Extraction failed for {filepath}: {e}")
        return []

    # List extracted files
    try:
        for root, dirs, files in os.walk(extract_to):
            for f in files:
                extracted_files.append(os.path.join(root, f))
        logger.debug(f"Successfully extracted {len(extracted_files)} files")
        return extracted_files
    finally:
        # Clean up secure temporary directory
        try:
            shutil.rmtree(extract_to)
            logger.debug(f"Cleaned up temporary directory: {extract_to}")
        except Exception as e:
            logger.warning(f"Failed to clean up temporary directory {extract_to}: {e}")
