import argparse
from utils.config import Config
from crawler.crawler import Crawler
from indexer.indexer import build_index, run_indexer
import time


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
    
    # add a flag to trigger the indexing phase
    parser.add_argument(
        "--index",
        action="store_true",
        help="Build the inverted index from the downloaded corpus."
    )
    
    # add a flag to trigger the interactive search console
    parser.add_argument(
        "--search",
        action="store_true",
        help="Start the interactive search engine terminal."
    )
    
    # parse the terminal commands
    args: argparse.Namespace = parser.parse_args()
    
    # if the user passed the index flag, build the index and exit immediately
    if args.index:
        print("=" * 50)
        print("BUILDING AND OPTIMIZING INVERTED INDEX")
        print("=" * 50)
        
        from indexer.indexer import run_indexer
        from indexer.pagerank import compute_pagerank
        from indexer.optimize import optimize_index
        
        # build the master json index
        run_indexer("data/corpus")
        
        # compute the link graph math
        compute_pagerank()
        
        # pack the json into binary files for high speed lookup
        optimize_index()
        
        return

    # if the user passed the search flag, spin up the interactive prompt
    if args.search:
        from search.engine import SearchEngine
        
        print("=" * 50)
        print("STARTING SEARCH ENGINE")
        print("=" * 50)
        
        engine: SearchEngine = SearchEngine("data/index")
        
        print("\nType your query and press Enter. Type 'q' or 'quit' to exit.")
        while True:
            try:
                query: str = input("\nSearch> ").strip()
                if not query:
                    continue
                if query.lower() in ("quit", "exit", "q"):
                    break
                    
                t0: float = time.perf_counter()
                results: list[tuple[str, float]] = engine.search(query, top_k=5)
                elapsed_ms: float = (time.perf_counter() - t0) * 1000
                
                print(f"Query: '{query}' ({elapsed_ms:.1f} ms)")
                if not results:
                    print("  No results found.")
                else:
                    for i, (url, score) in enumerate(results, 1):
                        print(f"  {i}. {url} (Score: {score:.4f})")
                        
            except (KeyboardInterrupt, EOFError):
                break
                
        engine.close()
        print("\nGoodbye!")
        return
    
    # initialize global configuration for the crawler
    config: Config = Config()
    
    # print a clean startup banner
    print("=" * 50)
    print("WEB CRAWLER PIPELINE")
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
