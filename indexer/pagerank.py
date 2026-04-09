import json
import logging
from collections import defaultdict

# configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger: logging.Logger = logging.getLogger(__name__)

# standard pagerank constants
DAMPING: float = 0.85
ITERATIONS: int = 50


def compute_pagerank() -> None:
    """
    Compute PageRank from the link graph and save normalized scores.
    Uses power iteration to calculate authority propagation.
    """
    logger.info("Loading link graph and doc map...")
    try:
        with open("data/index/links.json", "r", encoding="utf-8") as f:
            raw_links: dict[str, list[str]] = json.load(f)
        with open("data/index/doc_map.json", "r", encoding="utf-8") as f:
            doc_map: dict[str, str] = json.load(f)
    except FileNotFoundError:
        logger.error("Missing links.json or doc_map.json. Run indexer first.")
        return

    # map valid urls to their integer document ids
    url_to_id: dict[str, int] = {v: int(k) for k, v in doc_map.items()}
    indexed_ids: set[int] = set(url_to_id.values())
    n: int = len(indexed_ids)
    
    if n == 0:
        logger.warning("No indexed documents found.")
        return

    logger.info(f"{n:,} indexed documents, {len(raw_links):,} source URLs.")

    # build adjacency list strictly for indexed pages
    out_links: dict[int, set[int]] = defaultdict(set)
    in_links: dict[int, set[int]] = defaultdict(set)
    
    for src_url, targets in raw_links.items():
        if src_url not in url_to_id:
            continue
            
        src_id: int = url_to_id[src_url]
        for tgt_url in targets:
            if tgt_url in url_to_id:
                tgt_id: int = url_to_id[tgt_url]
                # ignore self-links
                if tgt_id != src_id:
                    out_links[src_id].add(tgt_id)
                    in_links[tgt_id].add(src_id)

    # uniform initialization
    pr: dict[int, float] = {doc_id: 1.0 / n for doc_id in indexed_ids}

    # pagerank power iteration
    logger.info("Starting PageRank iterations...")
    for iteration in range(ITERATIONS):
        new_pr: dict[int, float] = {}
        for doc_id in indexed_ids:
            # sum contributions from all pages that link to this page
            rank_sum: float = sum(
                pr[j] / len(out_links[j])
                for j in in_links[doc_id]
                if out_links[j]
            )
            new_pr[doc_id] = (1.0 - DAMPING) / n + DAMPING * rank_sum
            
        pr = new_pr
        if (iteration + 1) % 10 == 0:
            logger.info(f"Completed iteration {iteration + 1}/{ITERATIONS}")

    # normalize scores to a 0.0 - 1.0 multiplier range
    max_pr: float = max(pr.values()) if pr else 1.0
    pr_norm: dict[str, float] = {str(k): v / max_pr for k, v in pr.items()}

    with open("data/index/pagerank.json", "w", encoding="utf-8") as f:
        json.dump(pr_norm, f)
        
    logger.info(f"PageRank saved for {len(pr_norm):,} documents.")
