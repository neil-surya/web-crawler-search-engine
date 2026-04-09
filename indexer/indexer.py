import os
import json
import hashlib
import logging
from urllib.parse import urljoin, urldefrag
from collections import defaultdict
from bs4 import BeautifulSoup
from typing import Generator, Any

from utils.text_processing import (
    tokenize,
    generate_simhash,
    is_near_duplicate,
    add_to_bands,
    NUM_BANDS
)

# configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger: logging.Logger = logging.getLogger(__name__)


def load_documents(corpus_dir: str) -> Generator[tuple[int, str, str], None, None]:
    """
    Walk the corpus directory and yield documents.

    Args:
        corpus_dir (str): Base directory containing the scraped data.

    Yields:
        tuple[int, str, str]: A tuple of (doc_id, url, html_content).
    """
    doc_id: int = 0
    for root, _, files in os.walk(corpus_dir):
        for file in files:
            if not file.endswith(".json"):
                continue
                
            filepath: str = os.path.join(root, file)
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    data: dict[str, str] = json.load(f)
            except Exception as e:
                logger.warning(f"Skipping {filepath}: {e}")
                continue
                
            url: str = data.get("url", "")
            content: str = data.get("content", "")
            
            if url and content:
                yield doc_id, url, content
                doc_id += 1


def get_important_tokens(soup: BeautifulSoup) -> set[str]:
    """
    Extract tokens from high-signal HTML tags for scoring boosts.

    Args:
        soup (BeautifulSoup): Parsed HTML object.

    Returns:
        set[str]: Unique tokens found in important tags.
    """
    important: set[str] = set()
    for tag in soup.find_all(["title", "h1", "h2", "h3", "b", "strong"]):
        text: str = tag.get_text()
        tokens: list[str] = tokenize(text, apply_stemming=True, filter_stopwords=True)
        important.update(tokens)
    return important


def compute_tf(tokens: list[str]) -> dict[str, int]:
    """Calculate raw term frequency for a token list."""
    tf: dict[str, int] = defaultdict(int)
    for token in tokens:
        tf[token] += 1
    return dict(tf)


def dump_partial(partial_index: dict[str, list[dict[str, Any]]], dump_num: int) -> str:
    """Write the current in-memory partial index to disk and return the path."""
    os.makedirs("data/partial_indexes", exist_ok=True)
    path: str = f"data/partial_indexes/partial_{dump_num}.json"
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(partial_index, f)
        
    logger.info(f"Dumped partial index #{dump_num} to {path}")
    return path


def collect_anchor_text(corpus_dir: str) -> dict[str, list[str]]:
    """
    Pass 1: Collect anchor text and build the link graph for PageRank.

    Args:
        corpus_dir (str): Directory containing downloaded HTML files.

    Returns:
        dict[str, list[str]]: Map of target URLs to their incoming anchor tokens.
    """
    anchor_map: dict[str, list[str]] = defaultdict(list)
    link_graph: dict[str, set[str]] = defaultdict(set)
    
    for _, url, content in load_documents(corpus_dir):
        soup: BeautifulSoup = BeautifulSoup(content, "html.parser")
        
        for a in soup.find_all("a", href=True):
            href: str = a["href"].strip()
            
            if not href or href.startswith(("javascript:", "mailto:", "#")):
                continue
                
            try:
                target, _ = urldefrag(urljoin(url, href))
            except ValueError:
                continue
                
            link_graph[url].add(target)
            text: str = a.get_text().strip()
            
            if text:
                anchor_map[target].extend(tokenize(text, apply_stemming=True, filter_stopwords=True))
                
    os.makedirs("data/index", exist_ok=True)
    
    # save link graph for the pagerank module
    with open("data/index/links.json", "w", encoding="utf-8") as f:
        json.dump({k: list(v) for k, v in link_graph.items()}, f)
        
    logger.info(f"Link graph: {len(link_graph):,} source URLs saved.")
    return dict(anchor_map)


def build_index(corpus_dir: str, anchor_map: dict[str, list[str]]) -> list[str]:
    """
    Pass 2: Build the inverted index with duplicate detection and bigrams.

    Args:
        corpus_dir (str): Directory containing downloaded HTML files.
        anchor_map (dict[str, list[str]]): Incoming anchor tokens per URL.

    Returns:
        list[str]: Paths to the generated partial index files.
    """
    dump_every: int = 10000
    partial_index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    partial_files: list[str] = []
    doc_map: dict[int, str] = {}
    dump_num: int = 0
    
    seen_hashes: set[str] = set()
    bands_table: list[dict[int, list[int]]] = [{} for _ in range(NUM_BANDS)]
    duplicates_skipped: int = 0

    for doc_id, url, content in load_documents(corpus_dir):
        soup: BeautifulSoup = BeautifulSoup(content, "html.parser")

        # strip boilerplate
        for tag in soup.find_all(["nav", "footer", "aside"]):
            tag.decompose()
            
        text: str = soup.get_text(separator=" ", strip=True)

        # skip exact duplicates
        content_hash: str = hashlib.md5(text.encode("utf-8", errors="ignore")).hexdigest()
        if content_hash in seen_hashes:
            duplicates_skipped += 1
            continue
        seen_hashes.add(content_hash)

        # tokenize and check near-duplicates via simhash
        tokens: list[str] = tokenize(text, apply_stemming=True, filter_stopwords=True)
        fp: int = generate_simhash(tokens)
        
        if is_near_duplicate(fp, bands_table):
            duplicates_skipped += 1
            continue
        add_to_bands(fp, bands_table)

        # register valid document
        doc_map[doc_id] = url
        important: set[str] = get_important_tokens(soup)

        # augment with incoming anchor text
        if anchor_map and url in anchor_map:
            anchor_tokens: list[str] = anchor_map[url]
            tokens.extend(anchor_tokens)
            important.update(anchor_tokens)

        # unigram postings
        tf: dict[str, int] = compute_tf(tokens)
        for token, freq in tf.items():
            posting: dict[str, Any] = {"doc_id": doc_id, "tf": freq, "important": token in important}
            partial_index[token].append(posting)

        # bigram postings for phrase bonus
        bigram_tf: dict[str, int] = defaultdict(int)
        for i in range(len(tokens) - 1):
            bigram_tf[f"{tokens[i]} {tokens[i+1]}"] += 1
            
        for bigram, freq in bigram_tf.items():
            partial_index[bigram].append({"doc_id": doc_id, "tf": freq, "important": False})

        # chunking to save memory
        if doc_id > 0 and doc_id % dump_every == 0:
            path: str = dump_partial(partial_index, dump_num)
            partial_files.append(path)
            partial_index.clear()
            dump_num += 1

        if doc_id % 1000 == 0 and doc_id > 0:
            logger.info(f"Processed {doc_id} documents...")

    # dump remaining
    if partial_index:
        path = dump_partial(partial_index, dump_num)
        partial_files.append(path)

    # save doc mapping
    os.makedirs("data/index", exist_ok=True)
    with open("data/index/doc_map.json", "w", encoding="utf-8") as f:
        json.dump(doc_map, f)
        
    logger.info(f"Duplicate pages skipped: {duplicates_skipped}")
    return partial_files


def merge_partial_indexes(partial_files: list[str]) -> None:
    """Merge all partial index files into the master index.json."""
    logger.info("Merging partial indexes...")
    merged_index: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for path in partial_files:
        with open(path, "r", encoding="utf-8") as f:
            partial_data: dict[str, list[dict[str, Any]]] = json.load(f)
            
        for token, postings in partial_data.items():
            merged_index[token].extend(postings)

    with open("data/index/index.json", "w", encoding="utf-8") as f:
        json.dump(merged_index, f)
        
    logger.info("Master index.json successfully created.")


def run_indexer(corpus_dir: str) -> None:
    """Execute the full two-pass indexing pipeline."""
    logger.info("Pass 1: collecting anchor text...")
    anchor_map: dict[str, list[str]] = collect_anchor_text(corpus_dir)
    
    logger.info("Pass 2: building index...")
    partial_files: list[str] = build_index(corpus_dir, anchor_map)
    
    merge_partial_indexes(partial_files)
