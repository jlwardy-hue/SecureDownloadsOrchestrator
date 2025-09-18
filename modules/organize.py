print ("Loaded NEW organize.py with OCR/content extraction and smart grouping!")
import os
import shutil
import hashlib
import logging
import re
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

IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".tiff", ".bmp"]

def file_hash(filepath):
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()

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
    org_dir = config['directories']['organized']
    base_name = os.path.basename(filepath)
    hash_val = file_hash(filepath)
    ext = os.path.splitext(filepath)[1].lower()

    # 1. PHOTOS GROUPING
    if ext in IMAGE_EXTENSIONS:
        dest_dir = os.path.join(org_dir, "Photos")
        os.makedirs(dest_dir, exist_ok=True)
    # 2. SPRINGFIELD GROUPING
    elif base_name.lower().startswith("springfield"):
        dest_dir = os.path.join(org_dir, "Springfield")
        os.makedirs(dest_dir, exist_ok=True)
    # 3. DEFAULT: SENDER/DATE
    else:
        text = extract_text(filepath)
        sender, sent_date = extract_sender_and_date(text)
        safe_sender = re.sub(r"[^a-zA-Z0-9@._-]", "_", sender)
        safe_date = sent_date if sent_date != "UnknownDate" else "UnknownDate"
        dest_dir = os.path.join(org_dir, safe_sender, safe_date)
        os.makedirs(dest_dir, exist_ok=True)

    dest_name = f"{hash_val[:8]}_{base_name}"
    dest_path = os.path.join(dest_dir, dest_name)

    if os.path.exists(dest_path):
        logger.info(f"Duplicate detected (hash): {filepath} == {dest_path}")
        os.remove(filepath)
        return dest_path

    shutil.move(filepath, dest_path)
    logger.info(f"Moved {filepath} to {dest_path}")
    return dest_path
