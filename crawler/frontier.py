import os
import shelve
import hashlib
from threading import RLock
from typing import Any, Optional

def get_urlhash(url: str) -> str:
    """Hash a URL for safe storage keys."""
    return hashlib.md5(url.encode("utf-8")).hexdigest()

class Frontier:
    """Manages the queue of URLs to be downloaded and persists state to avoid loops."""

    def __init__(self, config: Any, restart: bool) -> None:
        """
        Initialize the frontier and load previous state if resuming.

        Args:
            config (Any): Configuration object.
            restart (bool): If True, delete previous save data and start fresh.
        """
        self.config: Any = config
        self.to_be_downloaded: list[str] = []
        self.lock: RLock = RLock()
        self.completed_count: int = 0
        
        # safely extract the max pages limit, default to 100 if missing
        self.max_pages: int = getattr(self.config, "max_pages", 100)

        # ensure the save directory exists
        save_dir: str = os.path.dirname(self.config.save_file)
        if save_dir:
            os.makedirs(save_dir, exist_ok=True)

        # handle restarting and deleting old save files
        if restart:
            print("Restarting crawler, clearing old frontier state...")
            for ext in ["", ".bak", ".dat", ".dir", ".db"]:
                path: str = f"{self.config.save_file}{ext}"
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass

        # open local database to store seen urls
        self.save: shelve.Shelf = shelve.open(self.config.save_file, writeback=True)
        
        if restart:
            # add seed urls to start a fresh crawl
            for url in self.config.seed_urls:
                self.add_url(url)
        else:
            # load existing state from the save file
            self._parse_save_file()
            if not self.to_be_downloaded:
                for url in self.config.seed_urls:
                    self.add_url(url)

    def _parse_save_file(self) -> None:
        """Load incomplete URLs from the database into the active queue."""
        total_count: int = len(self.save)
        tbd_count: int = 0
        
        for urlhash, data in self.save.items():
            url, completed = data
            if completed:
                self.completed_count += 1
            else:
                self.to_be_downloaded.append(url)
                tbd_count += 1
                
        print(f"Frontier loaded: {self.completed_count} completed, {tbd_count} pending.")

    def get_tbd_url(self) -> Optional[str]:
        """
        Safely pop the next URL from the queue.

        Returns:
            Optional[str]: The next URL, or None if the queue is empty or limit reached.
        """
        with self.lock:
            # hard shutdown if we hit our storage/safety limit
            if self.completed_count >= self.max_pages:
                return None
                
            try:
                return self.to_be_downloaded.pop()
            except IndexError:
                return None

    def add_url(self, url: str) -> None:
        """
        Add a new URL to the queue if it hasn't been seen before.

        Args:
            url (str): The URL to add.
        """
        urlhash: str = get_urlhash(url)
        with self.lock:
            # only add if we've never seen this exact url
            if urlhash not in self.save:
                self.save[urlhash] = (url, False)
                self.save.sync()
                self.to_be_downloaded.append(url)

    def mark_url_complete(self, url: str) -> None:
        """
        Mark a URL as successfully downloaded.

        Args:
            url (str): The URL to mark complete.
        """
        urlhash: str = get_urlhash(url)
        with self.lock:
            if urlhash in self.save:
                self.save[urlhash] = (url, True)
                self.save.sync()
                self.completed_count += 1
