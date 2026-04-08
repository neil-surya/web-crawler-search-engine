from typing import Any
from crawler.frontier import Frontier
from crawler.worker import Worker

class Crawler:
    """Main orchestrator that manages worker threads and the frontier."""

    def __init__(self, config: Any, restart: bool) -> None:
        """
        Initialize the crawler engine.

        Args:
            config (Any): Global configuration object.
            restart (bool): Flag to determine if the frontier should reset.
        """
        self.config: Any = config
        self.frontier: Frontier = Frontier(config, restart)
        self.workers: list[Worker] = []

    def start(self) -> None:
        """Spin up worker threads and begin crawling."""
        print(f"Starting crawl with {self.config.threads_count} workers...")
        
        # create and start all worker threads
        for worker_id in range(self.config.threads_count):
            worker: Worker = Worker(worker_id, self.config, self.frontier)
            self.workers.append(worker)
            worker.start()
            
        # block the main thread until all workers finish
        self.join()

    def join(self) -> None:
        """Wait for all worker threads to terminate."""
        for worker in self.workers:
            worker.join()
        
        print("Crawl finished. All workers shut down safely.")
