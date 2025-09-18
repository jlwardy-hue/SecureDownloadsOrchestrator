import time
import os
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Initialize logging for the monitor module
logger = logging.getLogger("Orchestrator.Monitor")
logger.debug("File monitoring module initialized")

class FolderMonitor:
    def __init__(self, directory, callback):
        self.directory = directory
        self.callback = callback

    def start(self):
        event_handler = Handler(self.callback)
        observer = Observer()
        observer.schedule(event_handler, self.directory, recursive=False)
        observer.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()

class Handler(FileSystemEventHandler):
    def __init__(self, callback):
        self.callback = callback
        self.processed_files = set()
        self.logger = logging.getLogger("Orchestrator.Monitor")

    def on_created(self, event):
        if not event.is_directory:
            self._handle_file_event(event.src_path, "created")
    
    def on_moved(self, event):
        if not event.is_directory and hasattr(event, 'dest_path'):
            self._handle_file_event(event.dest_path, "moved")
    
    def on_closed(self, event):
        # Only handle close events for files that weren't created in this session
        if not event.is_directory:
            filepath = event.src_path
            if filepath not in self.processed_files and os.path.exists(filepath):
                self._handle_file_event(filepath, "closed")

    def _handle_file_event(self, filepath, event_type):
        """Handle file events with deduplication and better logging."""
        if filepath in self.processed_files:
            self.logger.debug(f"File already processed, skipping {event_type} event: {filepath}")
            return
            
        if not os.path.exists(filepath):
            self.logger.debug(f"File no longer exists for {event_type} event: {filepath}")
            return
            
        self.logger.debug(f"Processing {event_type} event for: {filepath}")
        self.processed_files.add(filepath)
        
        try:
            self.callback(filepath)
        except Exception as e:
            self.logger.error(f"Error processing file {filepath}: {e}")
            # Remove from processed set so it can be retried
            self.processed_files.discard(filepath)
