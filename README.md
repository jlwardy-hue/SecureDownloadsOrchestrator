# SecureDownloadsOrchestrator

A Python-based file monitoring and organization system that automatically processes, scans, and organizes files dropped into a watched directory.

## Features

- **Automated File Organization**: Intelligently organizes files into folders based on content type
  - **Photos Folder**: Images (`.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.tiff`, `.bmp`, `.svg`, `.ico`, `.raw`, `.heic`, `.heif`)
  - **Content-Based Folders**: Configurable keyword-based organization (e.g., business names, projects, subjects)
  - **Sender/Date Folders**: Other files organized by extracted sender and date information

- **Security Features**: 
  - Virus scanning with ClamAV
  - File quarantine capability  
  - Hash-based duplicate detection
  - Secure random temporary directories for archive extraction

- **Archive Support**: Automatically extracts and processes archives (`.zip`, `.tar`, `.rar`, `.7z`, etc.) using secure temporary directories

- **Metadata Extraction**: Creates searchable index of processed files

## Security Features

The SecureDownloadsOrchestrator implements several security hardening measures:

- **Secure Archive Extraction**: Uses cryptographically secure random temporary directories (`tempfile.mkdtemp()`) instead of predictable paths, preventing directory prediction attacks
- **Virus Scanning Integration**: ClamAV integration with quarantine capability for infected files  
- **Binary Content Handling**: Proper binary file processing without lossy encoding
- **Hash-based Deduplication**: SHA256 file hashing prevents duplicate processing
- **Safe File Organization**: Sanitized directory and filename handling
- **Comprehensive Logging**: Debug-level visibility into all security operations

## Installation

1. Clone this repository
2. Install dependencies: `pip install -r requirements.txt`
3. Install ClamAV: `sudo apt-get install clamav clamav-daemon` (Linux) or `brew install clamav` (macOS)
4. Configure `config.yaml` with your directories
5. Run: `python3 orchestrator.py`

## Configuration

Edit `config.yaml` to set up your directories and preferences:

```yaml
directories:
  watch: "/path/to/watch/folder"      # Where files are dropped
  organized: "/path/to/organized"     # Where files are organized
  quarantine: "/path/to/quarantine"   # Where infected files go
  logs: "./logs/orchestrator.log"     # Log file location

# Content-based organization: organize files containing specific keywords into named folders
content_organization:
  Springfield:  # Example folder for Springfield/Simpsons content
    - "springfield"
    - "simpsons"
    - "homer"
    - "bart"
  Business:  # Example: customize for your business documents
    - "company_name"
    - "business"
    - "contract"

log_level: "INFO"  # DEBUG, INFO, WARNING, ERROR
```

## File Organization Logic

### Photos Folder
Files with image extensions are automatically moved to `organized/Photos/`:
- Supported formats: PNG, JPG, JPEG, GIF, WebP, TIFF, BMP, SVG, ICO, RAW, HEIC, HEIF

### Content-Based Organization (Configurable)
Files containing specific keywords in their filename are moved to corresponding folders. This is fully configurable in `config.yaml`:

**Example Configuration:**
```yaml
content_organization:
  Springfield:  # Example: Simpsons content
    - "springfield"
    - "simpsons" 
    - "homer"
    - "bart"
    - "lisa"
    - "marge"
  Business:  # Example: Business documents
    - "company_name"
    - "business"
    - "contract"
    - "invoice"
  ProjectAlpha:  # Example: Project files
    - "project_alpha" 
    - "alpha"
```

**How it works:**
- Files containing any configured keyword are moved to the corresponding folder
- Keywords are matched case-insensitively against the filename
- You can configure any number of keyword groups for different organizations (business names, projects, subjects, etc.)
- Springfield is provided as a working example - customize for your needs

### Default Organization
Other files are organized by extracted sender and date into folders like:
`organized/sender_name/2024-01-15/`

## Troubleshooting

### Issue: Files not being organized into Photos or Content-Based folders

**Symptoms**: Image files or keyword-matching files end up in sender/date folders instead of Photos/Content folders

**Solutions**:
1. **Check file extensions**: Ensure image files have supported extensions (case-insensitive)
2. **Verify keyword configuration**: Check `content_organization` section in config.yaml
3. **Test keyword matching**: File name must contain one of the configured keywords (case-insensitive)
4. **Check logs**: Enable DEBUG logging to see file processing details

```bash
# Enable debug logging
echo 'log_level: "DEBUG"' >> config.yaml

# Watch logs in real-time
tail -f logs/orchestrator.log
```

### Issue: Permission denied errors

**Symptoms**: `PermissionError` when accessing directories

**Solutions**:
1. **Check directory permissions**:
```bash
ls -la /path/to/watch/folder
chmod 755 /path/to/watch/folder  # If needed
```

2. **Ensure directories exist**:
```bash
mkdir -p /path/to/watch/folder
mkdir -p /path/to/organized/folder
mkdir -p /path/to/quarantine/folder
```

3. **Run with appropriate user permissions**

### Issue: Watch directory not found

**Symptoms**: `FileNotFoundError: [Errno 2] No such file or directory`

**Solutions**:
1. **Create the watch directory**:
```bash
mkdir -p /path/to/watch/folder
```

2. **Update config.yaml** with correct paths
3. **Use absolute paths** in configuration

### Issue: Duplicate file events causing errors

**Symptoms**: `Error organizing file: No such file or directory` after successful organization

**Solutions**:
- This is normal behavior - the enhanced monitoring system now handles duplicate events automatically
- Files are processed once and subsequent events are ignored
- Check logs to confirm successful organization

### Issue: ClamAV not working

**Symptoms**: Virus scanning errors or files not being scanned

**Solutions**:
1. **Install ClamAV**:
```bash
# Ubuntu/Debian
sudo apt-get update && sudo apt-get install clamav

# macOS  
brew install clamav

# Windows - Download from https://www.clamav.net/
```

2. **Update virus definitions**:
```bash
sudo freshclam
```

3. **Test ClamAV installation**:
```bash
clamscan --version
```

4. **Mock ClamAV for testing** (update config.yaml):
```yaml
virus_scanning:
  clamscan_path: "echo"  # Uses echo instead of clamscan
```

### Issue: Files not being detected

**Symptoms**: No file processing events when files are added

**Solutions**:
1. **Check if orchestrator is running**: Look for "SecureDownloads Orchestrator started" in logs
2. **Verify file system events**: Some network drives or virtual filesystems may not trigger events
3. **Test with local files**: Copy files directly to the watch folder
4. **Check file permissions**: Ensure files are readable

### Issue: Archive extraction failures

**Symptoms**: Archive files not being extracted or processed

**Solutions**:
1. **Install extraction tools**:
```bash
# For RAR files
sudo apt-get install unrar

# For 7z files  
sudo apt-get install p7zip-full
```

2. **Check archive extensions** in config.yaml
3. **Verify archive integrity**: Test with a known good archive

## Debugging Steps

### Enable Debug Logging
1. Set `log_level: "DEBUG"` in config.yaml
2. Restart the orchestrator
3. Monitor logs: `tail -f logs/orchestrator.log`

### Manual File Testing
Test file organization without monitoring:
```python
import yaml
from modules.organize import organize_file

with open('config.yaml') as f:
    config = yaml.safe_load(f)

# Test a specific file
result = organize_file('/path/to/test/file.jpg', config)
print(f"Organized to: {result}")
```

### Check Configuration
Verify your configuration is valid:
```python
import yaml
with open('config.yaml') as f:
    config = yaml.safe_load(f)
    print("Configuration loaded successfully:")
    print(yaml.dump(config, default_flow_style=False))
```

### Common Log Messages

- `"Successfully organized: filename -> destination"` - File processed correctly
- `"Duplicate detected (hash): source == destination"` - Duplicate file found and removed
- `"File no longer exists, skipping"` - Normal for duplicate events
- `"Identified as image file, organizing to Photos folder"` - Photos organization working
- `"Identified as [FolderName] file, organizing to [FolderName] folder"` - Content-based organization working
- `"Processing as default file type, extracting text content"` - Default sender/date organization

## File Processing Flow

1. **File Detection**: Watchdog monitors the watch directory for new files
2. **Duplicate Event Filtering**: Multiple events for the same file are deduplicated  
3. **File Validation**: Check if file still exists and is readable
4. **Virus Scanning**: ClamAV scans file for threats
5. **Archive Extraction**: If archive, extract contents and process each file
6. **File Organization**: 
   - Images → Photos folder
   - Springfield files → Springfield folder  
   - Others → Sender/Date folders
7. **Duplicate Detection**: Hash-based duplicate removal
8. **Metadata Extraction**: Index file information for searching

## Support

If you continue to have issues:
1. Check the logs with DEBUG level enabled
2. Verify all dependencies are installed correctly
3. Test with simple files first (like .txt or .jpg)
4. Ensure proper file and directory permissions
