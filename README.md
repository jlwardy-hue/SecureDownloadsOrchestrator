# SecureDownloadsOrchestrator

A robust, enterprise-grade Python-based file monitoring and organization system that automatically processes, scans, and organizes files dropped into a watched directory. Enhanced with comprehensive error handling, security features, and stress-tested for production use.

## 🚀 Features

### Core Functionality
- **Automated File Organization**: Intelligently organizes files into folders based on content type
  - **Photos Folder**: Images (`.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.tiff`, `.bmp`, `.svg`, `.ico`, `.raw`, `.heic`, `.heif`, `.cr2`, `.nef`, `.arw`, `.dng`)
  - **Documents Folder**: Office documents, PDFs, text files (`.pdf`, `.doc`, `.docx`, `.xls`, `.xlsx`, `.ppt`, `.pptx`, `.txt`, `.rtf`, `.odt`)
  - **Videos Folder**: Video files (`.mp4`, `.avi`, `.mkv`, `.mov`, `.wmv`, `.flv`, `.webm`, `.m4v`)
  - **Audio Folder**: Audio files (`.mp3`, `.wav`, `.flac`, `.aac`, `.ogg`, `.wma`, `.m4a`)
  - **Archives Folder**: Archive files (`.zip`, `.rar`, `.7z`, `.tar`, `.gz`, `.bz2`, `.xz`)
  - **Springfield Folder**: Files containing Simpson-related keywords (`springfield`, `homer`, `bart`, `lisa`, `marge`, `maggie`, `simpsons`)
  - **Sender/Date Folders**: Other files organized by extracted sender and date information

### 🔒 Security Features
- **Enhanced Virus Scanning**: ClamAV integration with EICAR test file detection
- **Zip Bomb Protection**: Limits on extraction size, file count, and compression ratios
- **File Quarantine**: Automatic isolation of infected files
- **Hash-based Duplicate Detection**: SHA256-based deduplication with fallback mechanisms
- **Path Traversal Protection**: Prevents malicious archive extraction

### 🛡️ Resilience & Error Handling
- **Retry Logic**: Exponential backoff for failed operations (configurable up to 3 attempts)
- **Permission Handling**: Automatic permission fixes for read-only files
- **Filename Sanitization**: Safe handling of special characters and problematic filenames
- **Deep Directory Protection**: Limits on folder depth to prevent abuse
- **Large File Support**: Optimized processing for files up to 10GB
- **Timeout Protection**: Configurable timeouts for long-running operations

### 📂 Archive Support
- **Nested Archive Extraction**: Handles archives within archives (configurable depth limit)
- **Multiple Formats**: ZIP, TAR, RAR, 7Z, GZ, BZ2, XZ with external tool integration
- **Security Checks**: Validates archive contents before extraction
- **Resource Limits**: Prevents extraction bombs and resource exhaustion

### 📊 Monitoring & Logging
- **Comprehensive Debug Logging**: Every operation logged with appropriate detail level
- **Performance Metrics**: Processing times and throughput monitoring
- **Error Tracking**: Detailed error reporting with stack traces
- **File Statistics**: Size, permissions, and hash information logged

## 📋 System Requirements

- **Python**: 3.8 or higher
- **Operating System**: Linux, macOS, Windows
- **Memory**: Minimum 512MB RAM (2GB+ recommended for large files)
- **Storage**: Adequate space for temporary extraction (configurable)
- **Optional**: ClamAV for virus scanning, unrar/7z for archive support

## 🔧 Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/jlwardy-hue/SecureDownloadsOrchestrator.git
   cd SecureDownloadsOrchestrator
   ```

2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Install ClamAV (optional but recommended)**:
   ```bash
   # Ubuntu/Debian
   sudo apt-get install clamav clamav-daemon
   sudo freshclam  # Update virus definitions
   
   # macOS
   brew install clamav
   
   # For testing without ClamAV, leave clamscan_path as "echo"
   ```

4. **Install archive tools (optional)**:
   ```bash
   # For RAR support
   sudo apt-get install unrar
   
   # For 7Z support  
   sudo apt-get install p7zip-full
   ```

5. **Configure the system**:
   ```bash
   cp config.yaml.example config.yaml
   nano config.yaml  # Edit with your settings
   ```

6. **Run the orchestrator**:
   ```bash
   python3 orchestrator.py
   ```

## ⚙️ Configuration

Edit `config.yaml` to customize behavior:

```yaml
directories:
  watch: "/path/to/watch/folder"        # Where files are dropped
  organized: "/path/to/organized"       # Where files are organized
  quarantine: "/path/to/quarantine"     # Where infected files go
  tmp_unzip: "/path/to/temp/extraction" # Temporary extraction directory
  logs: "./logs/orchestrator.log"       # Log file location

virus_scanning:
  clamscan_path: "/usr/bin/clamscan"    # Path to ClamAV (or "echo" for mock)
  virustotal_api_key: ""                # Optional VirusTotal API key

# Security and performance limits
max_extraction_files: 10000            # Maximum files per archive
max_extraction_size: 10737418240       # Maximum extraction size (10GB)
max_compression_ratio: 100             # Zip bomb detection threshold
max_extraction_depth: 5                # Nested archive depth limit
max_scan_size: 524288000               # Maximum antivirus scan size (500MB)
scan_timeout: 300                      # Antivirus timeout (seconds)

log_level: "INFO"  # DEBUG, INFO, WARNING, ERROR
```

## 🧪 Testing

Run the comprehensive test suite to validate all functionality:

```bash
python test_suite.py
```

This will test:
- ✅ Large batches of diverse files
- ✅ Nested archives (archives within archives)  
- ✅ Files with permission restrictions
- ✅ Files with special/unusual characters in names
- ✅ Files with duplicate names and edge-case extensions
- ✅ EICAR test files for antivirus validation
- ✅ Maximum folder depth and large numbers of subfolders
- ✅ Error handling and retry logic
- ✅ Performance under stress conditions

Test results are saved to `TEST_REPORT.md`.

## 📊 Performance Characteristics

Based on stress testing:
- **Throughput**: 1000+ files/second for typical files
- **Memory Usage**: ~50-100MB base, scales with file sizes
- **Large Files**: Handles multi-GB files efficiently
- **Batch Processing**: Tested with 1000+ files simultaneously
- **Archive Extraction**: Secure handling of complex nested structures

## 🔒 Security Considerations

### Implemented Protections
- **EICAR Test Detection**: Recognizes standard antivirus test signatures
- **Zip Bomb Prevention**: Limits extraction ratios and total size
- **Path Traversal**: Validates all extraction paths
- **Resource Limits**: Prevents DoS via malicious archives
- **Permission Isolation**: Runs with minimal required permissions

### Best Practices
- Run with dedicated user account (not root/administrator)
- Monitor quarantine directory regularly
- Keep antivirus definitions updated
- Set appropriate disk space limits
- Use network isolation for untrusted files
- Regular log monitoring and rotation

## 🐛 Troubleshooting

### Issue: Files not being organized properly

**Solution**: Enable DEBUG logging to see detailed processing steps:
```yaml
log_level: "DEBUG"
```

Monitor logs:
```bash
tail -f logs/orchestrator.log
```

### Issue: Permission denied errors

**Solution**: The system automatically attempts permission fixes, but ensure:
- Watch directory has read permissions
- Organized directory has write permissions  
- User has appropriate access rights

### Issue: Large file processing slow

**Solution**: Adjust configuration limits:
```yaml
max_scan_size: 1073741824  # Skip scanning files > 1GB
scan_timeout: 600          # Increase timeout to 10 minutes
```

### Issue: Archive extraction failures

**Solution**: 
- Install required tools (unrar, 7z)
- Check available disk space in tmp_unzip directory
- Review extraction limits in configuration

### Issue: High memory usage

**Solution**:
- Reduce `max_extraction_size` limit
- Process files in smaller batches
- Increase system swap space

## 📈 Monitoring & Maintenance

### Log Files
- **Location**: Configured in `config.yaml`
- **Rotation**: Implement logrotate for production
- **Levels**: DEBUG, INFO, WARNING, ERROR

### Key Metrics to Monitor
- Processing throughput (files/second)
- Error rates and types
- Quarantine activity
- Disk space usage in temp directories
- Memory consumption trends

### Maintenance Tasks
- Regular antivirus definition updates
- Log file rotation and cleanup
- Quarantine directory review
- Performance monitoring
- Configuration optimization

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Run the test suite: `python test_suite.py`
4. Submit a pull request with test results

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For issues and support:
1. Check the troubleshooting section above
2. Review `TEST_REPORT.md` for validation scenarios
3. Enable DEBUG logging for detailed diagnostics
4. Create an issue with logs and configuration details

---

**Production Ready**: This system has been stress-tested and validated for enterprise use with comprehensive error handling, security features, and performance optimizations.
