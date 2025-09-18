import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

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

    def on_created(self, event):
        if not event.is_directory:
            self.callback(event.src_path)
    def on_moved(self, event):
        if not event.is_directory:
            self.callback(event.dest_path)
    def on_closed(self, event):
        if not event.is_directory:
            self.callback(event.src_path)
