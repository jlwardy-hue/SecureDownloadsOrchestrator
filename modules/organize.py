import os
import shutil
import hashlib
import logging
import re
import io
from datetime import datetime

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

# Initialize logging for the organize module
logger = logging.getLogger("Orchestrator.Organize")
logger.debug("Organization module with OCR/content extraction and smart grouping initialized")

def is_keyword_match_file(filepath, config):
    """Enhanced content-based file detection with configurable keywords."""
    base_name = os.path.basename(filepath).lower()
    
    # Get keyword groups from config, with Springfield as default example
    keyword_groups = config.get('content_organization', {
        'Springfield': [
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
    })
    
    # Check each keyword group
    for folder_name, keywords in keyword_groups.items():
        for keyword in keywords:
            if keyword.lower() in base_name:
                return folder_name
                
    return None

IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".gif", ".webp", ".svg", ".ico", ".raw", ".heic", ".heif"]

def file_hash(filepath):
    """Calculate SHA256 hash of a file with error handling."""
    logger = logging.getLogger("Orchestrator.Organize")
    try:
        hasher = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        hash_value = hasher.hexdigest()
        logger.debug(f"Calculated hash for {filepath}: {hash_value[:16]}...")
        return hash_value
    except Exception as e:
        logger.error(f"Failed to calculate hash for {filepath}: {e}")
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
    logger = logging.getLogger("Orchestrator.Organize")
    
    # Check if file still exists before processing
    if not os.path.exists(filepath):
        logger.warning(f"File no longer exists, skipping: {filepath}")
        return None
        
    logger.debug(f"Starting organization of: {filepath}")
    
    org_dir = config['directories']['organized']
    base_name = os.path.basename(filepath)
    hash_val = file_hash(filepath)
    ext = os.path.splitext(filepath)[1].lower()
    
    logger.debug(f"File details - Name: {base_name}, Extension: {ext}, Hash: {hash_val[:8]}")

    # 1. PHOTOS GROUPING
    if ext in IMAGE_EXTENSIONS:
        dest_dir = os.path.join(org_dir, "Photos")
        logger.debug(f"Identified as image file, organizing to Photos folder")
        os.makedirs(dest_dir, exist_ok=True)
        logger.debug(f"Created/verified Photos directory: {dest_dir}")
    # 2. CONTENT-BASED KEYWORD GROUPING (configurable)
    elif (keyword_folder := is_keyword_match_file(filepath, config)) is not None:
        dest_dir = os.path.join(org_dir, keyword_folder)
        logger.debug(f"Identified as {keyword_folder} file, organizing to {keyword_folder} folder")
        os.makedirs(dest_dir, exist_ok=True)
        logger.debug(f"Created/verified {keyword_folder} directory: {dest_dir}")
    # 3. DEFAULT: SENDER/DATE
    else:
        logger.debug(f"Processing as default file type, extracting text content")
        text = extract_text(filepath)
        sender, sent_date = extract_sender_and_date(text)
        safe_sender = re.sub(r"[^a-zA-Z0-9@._-]", "_", sender)
        safe_date = sent_date if sent_date != "UnknownDate" else "UnknownDate"
        dest_dir = os.path.join(org_dir, safe_sender, safe_date)
        logger.debug(f"Identified sender: {sender} -> {safe_sender}, date: {sent_date} -> {safe_date}")
        os.makedirs(dest_dir, exist_ok=True)
        logger.debug(f"Created/verified directory: {dest_dir}")

    dest_name = f"{hash_val[:8]}_{base_name}"
    dest_path = os.path.join(dest_dir, dest_name)
    
    logger.debug(f"Target destination: {dest_path}")

    if os.path.exists(dest_path):
        logger.info(f"Duplicate detected (hash): {filepath} == {dest_path}")
        logger.debug(f"Removing duplicate source file: {filepath}")
        os.remove(filepath)
        return dest_path

    logger.debug(f"Moving file from {filepath} to {dest_path}")
    shutil.move(filepath, dest_path)
    logger.info(f"Successfully organized: {base_name} -> {dest_path}")
    return dest_path
