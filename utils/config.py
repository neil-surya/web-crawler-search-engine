class Config:
    """Global configuration settings for the web crawler and indexer."""

    def __init__(self) -> None:
        """Initialize default crawler configurations."""
        
        # crawler identity
        self.user_agent: str = "web-crawler-search-engine/1.0 (Educational Project; hello_puff@yahoo.com)"
        
        # network settings
        self.timeout: int = 10
        
        # politeness delay (seconds to wait between requests)
        self.time_delay: float = 1.5
        
        # multithreading settings
        self.threads_count: int = 4
        
        # frontier save file for state persistence
        self.save_file: str = "data/frontier_state"
        
        # seed urls to begin crawling
        self.seed_urls: list[str] = [
            "https://liquipedia.net/rocketleague/Main_Page"
        ]
        
        # safety limit to prevent runaway crawling and storage bloat
        self.max_pages: int = 200
