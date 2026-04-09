import os
import json
from collections import defaultdict
from typing import Generator
from bs4 import BeautifulSoup

# import your custom tokenization logic
from utils.text_processing import tokenize 


def get_corpus_files(corpus_dir: str) -> Generator[str, None, None]:
    """
    Yield file paths for all JSON files recursively found in the corpus.
    Using a generator keeps our memory footprint tiny.

    Args:
        corpus_dir (str): Base directory containing the scraped data.

    Yields:
        str: Absolute or relative path to a single JSON file.
    """
    for root, _, files in os.walk(corpus_dir):
        for file in files:
            if file.endswith(".json"):
                yield os.path.join(root, file)


def build_index(corpus_dir: str, output_path: str) -> None:
    """
    Build an inverted index from the crawled corpus and save it to disk.
    
    Args:
        corpus_dir (str): Path to the directory containing downloaded HTML JSON files.
        output_path (str): Path where the final inverted index JSON will be saved.
    """
    print("Starting indexer...")
    
    # inverted_index maps tokens to a dict of {url: frequency}
    inverted_index: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    
    # document count for tracking progress in the terminal
    doc_count: int = 0
    
    # process each file one by one
    for filepath in get_corpus_files(corpus_dir):
        with open(filepath, "r", encoding="utf-8") as f:
            try:
                data: dict[str, str] = json.load(f)
            except json.JSONDecodeError:
                continue
                
        url: str = data.get("url", "")
        raw_html: str = data.get("content", "")
        
        # skip empty or malformed files
        if not url or not raw_html:
            continue
            
        # extract visible text from html, stripping out scripts and tags
        soup: BeautifulSoup = BeautifulSoup(raw_html, "html.parser")
        text: str = soup.get_text(separator=" ", strip=True)
        
        # tokenize the text, heavily utilizing your stopwords filter
        tokens: list[str] = tokenize(text, apply_stemming=True, filter_stopwords=True)
        
        # update index with term frequencies for this specific url
        for token in tokens:
            inverted_index[token][url] += 1
            
        doc_count += 1
        
        # print progress every 1,000 documents so you know it hasn't frozen
        if doc_count % 1000 == 0:
            print(f"Processed {doc_count} documents...")
            
    # save the completed master index to disk
    print(f"Writing index with {len(inverted_index)} unique terms to disk...")
    
    # ensure the target directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(inverted_index, f)
        
    print("Indexing complete! Data is ready for the Search UI.")
