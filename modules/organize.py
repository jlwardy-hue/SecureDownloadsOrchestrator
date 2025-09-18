import os
import shutil
import hashlib
import logging
import re
import unicodedata
import stat
import time
from datetime import datetime
from pathlib import Path

try:
    import pytesseract
    from PIL import Image
    import docx
    from pdfminer.high_level import extract_text as extract_pdf_text
except ImportError:
    pytesseract = None
    Image = None
    docx = None
    extract_pdf_text = None

def sanitize_filename(filename):
    """
    Sanitize filename by removing/replacing problematic characters.
    
    Args:
        filename: Original filename
        
    Returns:
        str: Sanitized filename safe for filesystem
    """
    # Normalize unicode characters
    filename = unicodedata.normalize('NFKD', filename)
    
    # Remove control characters
    filename = ''.join(char for char in filename if ord(char) >= 32)
    
    # Replace problematic characters with underscores
    problematic_chars = ['<', '>', ':', '"', '|', '?', '*', '\\', '/']
    for char in problematic_chars:
        filename = filename.replace(char, '_')
    
    # Replace multiple consecutive underscores/spaces/dots with single ones
    filename = re.sub(r'[_\s\.]+', lambda m: '_' if '_' in m.group() else m.group()[0], filename)
    
    # Remove leading/trailing whitespace and dots
    filename = filename.strip(' .')
    
    # Ensure filename is not empty and not a reserved name
    if not filename or filename.lower() in ['con', 'prn', 'aux', 'nul'] + [f'com{i}' for i in range(1, 10)] + [f'lpt{i}' for i in range(1, 10)]:
        filename = f"file_{int(time.time())}"
    
    # Limit length (keeping extension)
    name, ext = os.path.splitext(filename)
    max_name_length = 240 - len(ext)  # Leave room for extension and path limits
    if len(name) > max_name_length:
        name = name[:max_name_length]
        filename = name + ext
    
    return filename

def is_springfield_file(filepath):
    """Enhanced Springfield file detection with multiple criteria."""
    base_name = os.path.basename(filepath).lower()
    
    # Check various Springfield patterns
    springfield_patterns = [
        "springfield",
        "spring_field", 
        "spring-field",
        "simpsons",
        "homer",
        "marge",
        "bart",
        "lisa",
        "maggie"
    ]
    
    for pattern in springfield_patterns:
        if pattern in base_name:
            return True
            
    return False

IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".gif", ".webp", ".svg", ".ico", ".raw", ".heic", ".heif", ".cr2", ".nef", ".arw", ".dng"]

def safe_makedirs(path, mode=0o755, max_depth=50):
    """
    Safely create directories with depth limit and permission handling.
    
    Args:
        path: Directory path to create
        mode: Directory permissions
        max_depth: Maximum directory depth to prevent abuse
        
    Returns:
        bool: True if successful, False otherwise
    """
    logger = logging.getLogger("Orchestrator.Organize")
    
    try:
        # Check depth
        path_depth = len(Path(path).parts)
        if path_depth > max_depth:
            logger.error(f"Directory path too deep ({path_depth} > {max_depth}): {path}")
            return False
        
        # Create directories
        os.makedirs(path, mode=mode, exist_ok=True)
        
        # Verify creation and permissions
        if os.path.exists(path) and os.access(path, os.W_OK):
            logger.debug(f"Successfully created/verified directory: {path}")
            return True
        else:
            logger.error(f"Directory creation failed or no write access: {path}")
            return False
            
    except OSError as e:
        logger.error(f"Failed to create directory {path}: {e}")
        return False

def file_hash(filepath):
    """Calculate SHA256 hash of a file with enhanced error handling."""
    logger = logging.getLogger("Orchestrator.Organize")
    try:
        hasher = hashlib.sha256()
        with open(filepath, "rb") as f:
            # Process file in chunks to handle large files
            while chunk := f.read(65536):  # 64KB chunks
                hasher.update(chunk)
        hash_value = hasher.hexdigest()
        logger.debug(f"Calculated hash for {filepath}: {hash_value[:16]}...")
        return hash_value
    except PermissionError as e:
        logger.error(f"Permission denied calculating hash for {filepath}: {e}")
        # Try to fix permissions and retry once
        try:
            os.chmod(filepath, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
            hasher = hashlib.sha256()
            with open(filepath, "rb") as f:
                while chunk := f.read(65536):
                    hasher.update(chunk)
            hash_value = hasher.hexdigest()
            logger.warning(f"Hash calculated after permission fix: {hash_value[:16]}...")
            return hash_value
        except Exception:
            pass
    except OSError as e:
        logger.error(f"Failed to calculate hash for {filepath}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error calculating hash for {filepath}: {e}")
    
    # Fallback to timestamp-based hash if file hash fails
    try:
        mtime = os.path.getmtime(filepath)
        fallback_hash = hashlib.sha256(f"{filepath}_{mtime}".encode()).hexdigest()
        logger.warning(f"Using fallback hash (mtime): {fallback_hash[:16]}...")
        return fallback_hash
    except Exception as mtime_exc:
        logger.warning(f"Could not get mtime for {filepath}: {mtime_exc}. Using current time for fallback hash.")
        now = datetime.utcnow().isoformat()
        fallback_hash = hashlib.sha256(f"{filepath}_{now}".encode()).hexdigest()
        logger.warning(f"Using fallback hash (now): {fallback_hash[:16]}...")
        return fallback_hash

def extract_text(filepath):
    ext = os.path.splitext(filepath)[1].lower()
    try:
        if ext == ".pdf" and extract_pdf_text is not None:
            text = extract_pdf_text(filepath)
            if text and text.strip():
                return text
        elif ext == ".docx" and docx is not None:
            doc = docx.Document(filepath)
            return "\n".join([p.text for p in doc.paragraphs])
        elif ext in [".txt", ".csv", ".md"]:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        elif ext in IMAGE_EXTENSIONS and pytesseract and Image:
            image = Image.open(filepath)
            return pytesseract.image_to_string(image)
        # Fallback: try OCR for anything else (e.g. scanned PDFs as images)
        if pytesseract and Image:
            try:
                image = Image.open(filepath)
                return pytesseract.image_to_string(image)
            except Exception:
                pass
    except Exception as e:
        logging.getLogger("Orchestrator.Organize").warning(f"Text extraction failed for {filepath}: {e}")
    return ""

EMAIL_RE = re.compile(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)")
DATE_RE = re.compile(
    r"((?:19|20)\d{2}[-/. ](?:0[1-9]|1[0-2])[-/. ](?:0[1-9]|[12][0-9]|3[01])|" # YYYY-MM-DD
    r"(?:0[1-9]|[12][0-9]|3[01])[-/. ](?:0[1-9]|1[0-2])[-/. ](?:19|20)\d{2})"   # DD-MM-YYYY
)

def normalize_date(raw_date):
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y"):
        try:
            dt = datetime.strptime(raw_date, fmt)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            continue
    return "UnknownDate"

def extract_sender_and_date(text):
    email_match = EMAIL_RE.search(text)
    sender = email_match.group(1) if email_match else "UnknownSender"

    date_match = DATE_RE.search(text)
    if date_match:
        sent_date = normalize_date(date_match.group(0).replace(" ", "-").replace("/", "-").replace(".", "-"))
    else:
        sent_date = "UnknownDate"
    return sender, sent_date

def organize_file(filepath, config):
    """
    Enhanced file organization with robust error handling and edge case support.
    
    Args:
        filepath: Path to the file to organize
        config: Configuration dictionary
        
    Returns:
        str: Path to organized file or None if failed
    """
    logger = logging.getLogger("Orchestrator.Organize")
    
    # Check if file still exists before processing
    if not os.path.exists(filepath):
        logger.warning(f"File no longer exists, skipping: {filepath}")
        return None
    
    # Check file permissions
    if not os.access(filepath, os.R_OK):
        logger.error(f"No read permission for file: {filepath}")
        return None
        
    logger.debug(f"Starting organization of: {filepath}")
    
    try:
        org_dir = config['directories']['organized']
        base_name = os.path.basename(filepath)
        
        # Sanitize filename to handle special characters
        safe_base_name = sanitize_filename(base_name)
        if safe_base_name != base_name:
            logger.debug(f"Sanitized filename: {base_name} -> {safe_base_name}")
        
        hash_val = file_hash(filepath)
        if not hash_val:
            logger.error(f"Could not calculate hash for file: {filepath}")
            return None
            
        ext = os.path.splitext(safe_base_name)[1].lower()
        
        logger.debug(f"File details - Original: {base_name}, Sanitized: {safe_base_name}, Extension: {ext}, Hash: {hash_val[:8]}")

        # Enhanced file categorization
        dest_dir = None
        
        # 1. PHOTOS GROUPING - Enhanced with more formats
        if ext in IMAGE_EXTENSIONS:
            dest_dir = os.path.join(org_dir, "Photos")
            logger.debug(f"Identified as image file, organizing to Photos folder")
            
        # 2. SPRINGFIELD GROUPING - Enhanced detection
        elif is_springfield_file(filepath):
            dest_dir = os.path.join(org_dir, "Springfield")
            logger.debug(f"Identified as Springfield file, organizing to Springfield folder")
            
        # 3. ARCHIVE GROUPING - For extracted archives
        elif ext in ['.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz']:
            dest_dir = os.path.join(org_dir, "Archives")
            logger.debug(f"Identified as archive file, organizing to Archives folder")
            
        # 4. DOCUMENT GROUPING - Office documents, PDFs, etc.
        elif ext in ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.rtf', '.odt']:
            dest_dir = os.path.join(org_dir, "Documents")
            logger.debug(f"Identified as document file, organizing to Documents folder")
            
        # 5. VIDEO GROUPING
        elif ext in ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v']:
            dest_dir = os.path.join(org_dir, "Videos")
            logger.debug(f"Identified as video file, organizing to Videos folder")
            
        # 6. AUDIO GROUPING
        elif ext in ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', '.m4a']:
            dest_dir = os.path.join(org_dir, "Audio")
            logger.debug(f"Identified as audio file, organizing to Audio folder")
            
        # 7. DEFAULT: SENDER/DATE GROUPING
        else:
            logger.debug(f"Processing as default file type, extracting text content")
            try:
                text = extract_text(filepath)
                sender, sent_date = extract_sender_and_date(text)
                
                # Enhanced sender sanitization
                safe_sender = re.sub(r"[^a-zA-Z0-9@._-]", "_", sender)[:100]  # Limit length
                safe_date = sent_date if sent_date != "UnknownDate" else "UnknownDate"
                
                dest_dir = os.path.join(org_dir, safe_sender, safe_date)
                logger.debug(f"Identified sender: {sender} -> {safe_sender}, date: {sent_date} -> {safe_date}")
            except Exception as e:
                logger.warning(f"Error during text extraction, using fallback organization: {e}")
                dest_dir = os.path.join(org_dir, "Unsorted")

        # Create destination directory with enhanced error handling
        if not safe_makedirs(dest_dir):
            logger.error(f"Failed to create destination directory: {dest_dir}")
            # Fallback to a simpler directory structure
            fallback_dir = os.path.join(org_dir, "Unsorted")
            if not safe_makedirs(fallback_dir):
                logger.error(f"Failed to create fallback directory: {fallback_dir}")
                return None
            dest_dir = fallback_dir
            logger.warning(f"Using fallback directory: {dest_dir}")

        logger.debug(f"Created/verified directory: {dest_dir}")

        # Generate destination filename with hash prefix
        dest_name = f"{hash_val[:8]}_{safe_base_name}"
        dest_path = os.path.join(dest_dir, dest_name)
        
        # Handle very long paths
        if len(dest_path) > 250:  # Conservative limit for cross-platform compatibility
            # Truncate the filename part while keeping the hash and extension
            name_part, ext_part = os.path.splitext(safe_base_name)
            max_name_len = 250 - len(dest_dir) - len(hash_val[:8]) - len(ext_part) - 10  # Some buffer
            if max_name_len > 0:
                truncated_name = name_part[:max_name_len]
                dest_name = f"{hash_val[:8]}_{truncated_name}{ext_part}"
                dest_path = os.path.join(dest_dir, dest_name)
                logger.debug(f"Truncated long filename: {dest_name}")
            else:
                # Extreme case: use only hash as filename
                dest_name = f"{hash_val[:8]}{ext_part}"
                dest_path = os.path.join(dest_dir, dest_name)
                logger.warning(f"Using hash-only filename due to path length: {dest_name}")
        
        logger.debug(f"Target destination: {dest_path}")

        # Handle duplicates
        if os.path.exists(dest_path):
            logger.info(f"Duplicate detected (exact path exists): {filepath} == {dest_path}")
            
            # Compare file contents to ensure they're actually the same
            try:
                existing_hash = file_hash(dest_path)
                if existing_hash == hash_val:
                    logger.info(f"Confirmed duplicate (hash match): removing source file")
                    
                    # Safe removal with permission handling
                    try:
                        os.remove(filepath)
                        logger.debug(f"Successfully removed duplicate source file: {filepath}")
                    except PermissionError:
                        # Try to fix permissions and retry
                        try:
                            os.chmod(filepath, stat.S_IWRITE | stat.S_IREAD)
                            os.remove(filepath)
                            logger.debug(f"Removed duplicate after permission fix: {filepath}")
                        except Exception as e:
                            logger.error(f"Could not remove duplicate file: {e}")
                            return None
                    
                    return dest_path
                else:
                    # Different content, need to create a unique name
                    counter = 1
                    name_part, ext_part = os.path.splitext(dest_name)
                    while counter < 1000:  # Prevent infinite loop
                        unique_name = f"{name_part}_{counter}{ext_part}"
                        unique_path = os.path.join(dest_dir, unique_name)
                        if not os.path.exists(unique_path):
                            dest_path = unique_path
                            logger.debug(f"Created unique filename: {unique_name}")
                            break
                        counter += 1
                    else:
                        logger.error(f"Could not create unique filename after 1000 attempts")
                        return None
                        
            except Exception as e:
                logger.error(f"Error checking duplicate: {e}")
                return None

        # Move file to destination with enhanced error handling
        logger.debug(f"Moving file from {filepath} to {dest_path}")
        
        try:
            # First, try a simple move
            shutil.move(filepath, dest_path)
            logger.info(f"Successfully organized: {base_name} -> {dest_path}")
            
        except PermissionError as e:
            logger.warning(f"Permission error during move, attempting to fix: {e}")
            try:
                # Try to fix permissions and retry
                os.chmod(filepath, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
                shutil.move(filepath, dest_path)
                logger.info(f"Successfully organized after permission fix: {base_name} -> {dest_path}")
            except Exception as e2:
                logger.error(f"Failed to move file after permission fix: {e2}")
                return None
                
        except OSError as e:
            logger.error(f"OS error during move: {e}")
            # Try copy + delete as fallback
            try:
                logger.debug("Attempting copy + delete fallback")
                shutil.copy2(filepath, dest_path)  # Preserve metadata
                os.remove(filepath)
                logger.info(f"Successfully organized using copy+delete: {base_name} -> {dest_path}")
            except Exception as e2:
                logger.error(f"Copy+delete fallback also failed: {e2}")
                return None
                
        except Exception as e:
            logger.error(f"Unexpected error during move: {e}")
            return None
        
        # Verify the move was successful
        if os.path.exists(dest_path) and not os.path.exists(filepath):
            logger.debug(f"Move verification successful")
            return dest_path
        else:
            logger.error(f"Move verification failed - dest exists: {os.path.exists(dest_path)}, source exists: {os.path.exists(filepath)}")
            return None
            
    except Exception as e:
        logger.error(f"Unexpected error during file organization: {e}")
        return None
