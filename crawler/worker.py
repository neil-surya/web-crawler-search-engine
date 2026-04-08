import os
import json
import hashlib
import time
from threading import Thread
from urllib.parse import urlparse
from typing import Any, Optional

from utils.download import download
from crawler import scraper


class Worker(Thread):
    """Worker thread for downloading and saving web pages."""

    def __init__(self, worker_id: int, config: Any, frontier: Any) -> None:
        """
        Initialize the worker thread.

        Args:
            worker_id (int): Unique identifier for this worker.
            config (Any): Configuration object containing settings like politeness delay.
            frontier (Any): Queue manager for URLs to be processed.
        """
        super().__init__(daemon=True)
        self.worker_id: int = worker_id
        self.config: Any = config
        self.frontier: Any = frontier
        self.corpus_dir: str = "data/corpus"
        
        # ensure base corpus directory exists
        os.makedirs(self.corpus_dir, exist_ok=True)
        
    def save_document(self, url: str, html_content: bytes) -> None:
        """
        Save the scraped HTML to disk organized by subdomain.

        Args:
            url (str): The full URL of the saved document.
            html_content (bytes): The raw HTML content from the response.
        """
        parsed = urlparse(url)
        domain: str = parsed.hostname if parsed.hostname else "unknown_domain"
        
        # create a directory for this specific domain
        domain_dir: str = os.path.join(self.corpus_dir, domain)
        os.makedirs(domain_dir, exist_ok=True)
        
        # hash the url to create a unique, safe filename
        url_hash: str = hashlib.md5(url.encode('utf-8')).hexdigest()
        filepath: str = os.path.join(domain_dir, f"{url_hash}.json")
        
        # save exact format expected by the indexer
        doc_data: dict[str, str] = {
            "url": url,
            "content": html_content.decode('utf-8', errors='replace')
        }
        
        with open(filepath, "w", encoding='utf-8') as f:
            json.dump(doc_data, f)

    def run(self) -> None:
        """Continuously process URLs from the frontier until empty."""
        print(f"Worker-{self.worker_id} starting...")
        
        # setup a patience counter for empty queues
        empty_retries: int = 0
        max_retries: int = 15
        
        while True:
            # fetch the next url from the queue
            tbd_url: Optional[str] = self.frontier.get_tbd_url()
            
            # handle temporary empty queues (the startup bottleneck)
            if not tbd_url:
                if empty_retries < max_retries:
                    time.sleep(1.0)
                    empty_retries += 1
                    continue
                else:
                    print(f"Worker-{self.worker_id}: Frontier is permanently empty. Stopping.")
                    break
                    
            # reset retries once we successfully grab a url
            empty_retries = 0
                
            # download the page
            resp: Any = download(tbd_url, self.config)
            
            # if the download was successful, save the document
            if (resp and resp.status == 200 and resp.raw_response and 
                "text/html" in (resp.raw_response.headers.get("Content-Type") or "").lower()):
                self.save_document(tbd_url, resp.raw_response.content)
            
            # pass to scraper to get the next links
            scraped_urls: list[str] = scraper.scraper(tbd_url, resp)
            for scraped_url in scraped_urls:
                self.frontier.add_url(scraped_url)
                
            # mark url as processed and respect politeness delay
            self.frontier.mark_url_complete(tbd_url)
            time.sleep(self.config.time_delay)
