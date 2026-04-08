import argparse
from utils.config import Config
from crawler.crawler import Crawler

def main() -> None:
    """Main entry point for the Web Crawler and Search Engine pipeline."""
    
    # set up argument parser for cli controls
    parser = argparse.ArgumentParser(description="Web Crawler for Liquipedia Rocket League")
    
    # add a flag to let the user wipe the database and start fresh
    parser.add_argument(
        "--restart", 
        action="store_true", 
        help="Delete the existing frontier state and start a fresh crawl from the seed URLs."
    )
    
    # parse the terminal commands
    args: argparse.Namespace = parser.parse_args()
    
    # initialize global configuration
    config: Config = Config()
    
    # print a clean startup banner
    print("=" * 50)
    print("WEB CRAWLER & SEARCH ENGINE PIPELINE")
    print("=" * 50)
    print(f"Targeting: {config.seed_urls[0]}")
    print(f"Max Pages: {config.max_pages}")
    print(f"Threads:   {config.threads_count}")
    print("-" * 50)
    
    # initialize and start the engine
    crawler: Crawler = Crawler(config, args.restart)
    crawler.start()
    
    # print a clean shutdown banner
    print("=" * 50)
    print("Phase 1 (Crawling) Complete!")
    print("Data is safely stored in the 'data/corpus' directory.")
    print("=" * 50)

if __name__ == "__main__":
    main()
