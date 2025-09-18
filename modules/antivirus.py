import subprocess
import os
import logging

def scan_file(filepath, config):
    logger = logging.getLogger("Orchestrator.Antivirus")
    # Step 1: ClamAV
    clamscan = config['virus_scanning']['clamscan_path']
    quarantine = config['directories']['quarantine']
    os.makedirs(quarantine, exist_ok=True)
    result = subprocess.run([clamscan, "--move", quarantine, filepath], capture_output=True, text=True)
    logger.info(f"ClamAV: {result.stdout}")
    if os.path.exists(os.path.join(quarantine, os.path.basename(filepath))):
        return "quarantined"
    # (Optional) Step 2: VirusTotal
    vt_key = config['virus_scanning'].get('virustotal_api_key')
    if vt_key:
        # Placeholder: add VirusTotal scanning logic here
        pass
    return "clean"
