# Rocket League Liquipedia Search Engine

## Overview
As an avid follower of Rocket League Esports (RLCS), I wanted to build a tool I could actually use to query player stats, team histories, and tournament data at lightning speed. 

This project is a high-performance, full-stack search engine custom-built for the Rocket League Liquipedia wiki. It features a multithreaded web crawler, a disk-based inverted index, and a ranking algorithm utilizing BM25 and PageRank. 

This repository is a combined, refined, and heavily customized adaptation of two core projects from **CS 121 (Information Retrieval) at UC Irvine**. While the original academic projects were designed to crawl static, internal university servers, I rebuilt and optimized this architecture to operate on live, real-world data with sub-millisecond query times and a lightweight Flask web interface.

## ⚠️ Ethical Scraping & Rate Limiting Disclaimer
During the development and testing of this project, the crawler architecture worked flawlessly, achieving exceptional extraction speeds and perfect data structuring. However, despite strictly adhering to ethical crawling practices including parsing `robots.txt` and enforcing a strict politeness delay between requests, Liquipedia's automated Cloudflare protections eventually rate-limited the scraper.

Out of respect for Liquipedia's volunteer-run server infrastructure, I immediately and permanently halted the crawler. The engine was built to handle millions of pages, but the resulting corpus was intentionally capped at the completed 284 pages. 

**Please do not run this crawler against Liquipedia.** This repository serves strictly as an educational portfolio piece to demonstrate multithreading, inverted index construction, and search ranking algorithms. If you wish to test the crawler's capabilities, please point it toward a different, explicitly permissive domain.

## Features
* **Multithreaded Web Crawler:** Polite, concurrent scraping with a thread-safe URL Frontier and strict `robots.txt` compliance.
* **Near-Duplicate Detection:** 64-bit SimHash and Locality-Sensitive Hashing (LSH) to filter out duplicate pages.
* **Disk-Based Binary Indexing:** Custom binary struct packing that enables `O(log N)` disk lookups, bypassing RAM limitations.
* **Advanced Ranking:** TF-IDF/BM25 scoring combined with Bigram bonuses and PageRank authority multipliers.
* **Interactive UI:** A lightweight Flask web application delivering search results in **~0.2 milliseconds**.

## Tech Stack
* **Language:** Python 3.11+
* **Web Scraping:** `requests`, `BeautifulSoup4`
* **Text Processing:** `nltk` (PorterStemmer), Regex
* **Data Structures:** `shelve` (persistent queue), `array`, `struct` (binary packing)
* **Web Framework:** Flask

## Architecture & Pipeline

```text
1. CRAWLING                        2. INDEXING & MATH                 3. RETRIEVAL & UI
[Seed URLs]                        [HTML Corpus]                      [User Query]
    ↓                                    ↓                                  ↓
Multithreaded Workers          Two-Pass Extractor (BeautifulSoup)     Tokenize & Stem
    ↓                                    ↓                                  ↓
Politeness/Robots Check        SimHash / LSH Deduplication            O(log N) Binary Search
    ↓                                    ↓                                  ↓
HTML Corpus (JSON)             BM25 TF + PageRank Link Graph          BM25 + PageRank Math
                                         ↓                                  ↓
                               Binary Packer (struct/array)           Top K Ranked Results
                                         ↓                                  ↓
                               postings.bin & offsets.bin             Flask Web Interface
```

## How It Works

### 1. The Crawler (`crawler/`)
The crawler utilizes a thread-safe `Frontier` queue protected by an `RLock` to manage URLs across multiple worker threads. It respects a strict 1.5-second politeness delay and parses `robots.txt` to avoid server strain or IP bans. Pages are downloaded, stripped of unnecessary boilerplate, and saved locally as minified JSON files.

### 2. The Indexer & PageRank (`indexer/`)
A two-pass system parses the downloaded HTML:
* **Pass 1:** Constructs a directed link graph from `<a>` tags and computes global **PageRank** scores using power iteration.
* **Pass 2:** Tokenizes text, removes stopwords, applies Porter Stemming, and generates **SimHash** fingerprints. Locality-Sensitive Hashing (LSH) is used to detect and drop near-duplicate pages. It builds a massive in-memory inverted index mapping tokens to document frequencies.

### 3. Binary Optimization (`indexer/optimize.py`)
To prevent the search engine from requiring gigabytes of RAM, the massive JSON index is shredded into raw bytes. Posting lists are packed into a `postings.bin` file, and a compact lexicon is created using Python `array` and `struct`. This allows the engine to keep memory usage tiny while finding exact byte offsets via binary search.

### 4. The Search Engine (`search/engine.py` & `app.py`)
Queries are tokenized and binary-searched (`bisect`) against the memory-mapped offsets. The engine seeks to the exact byte on disk, reads the posting list, and ranks documents using **BM25 length-normalized scoring**, applying a 1.5x multiplier for Bigram phrase matches, and a multiplicative boost based on the URL's PageRank authority. 

## Installation & Setup

1. Clone the repository:
```bash
git clone github.com/neil-surya/web-crawler-search-engine.git
cd web-crawler-search-engine
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/Scripts/activate  # Windows
# source venv/bin/activate    # Mac/Linux
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

The pipeline is controlled via a centralized command-line interface.

**1. Run the Crawler**
*(Note: To respect Liquipedia's rate limits and Cloudflare protections, standard runs are capped at a safe sample size).*
```bash
python main.py --restart
```

**2. Build and Optimize the Index**
Parses the corpus, calculates PageRank, and packs the binary `.bin` files.
```bash
python main.py --index
```

**3. Launch the Web UI**
Starts the Flask server. Open `http://127.0.0.1:5000` in your browser.
```bash
python main.py --search
```

## What I Learned

* **Systems Engineering:** How to manage memory efficiently. Dropping JSON in favor of binary structs and byte-offset seeking reduced load times from ~27 seconds to ~2 seconds.
* **Multithreading:** Handling race conditions and thread starvation in Python using `RLock` and timeout loops to ensure safe `Ctrl+C` shutdowns.
* **Information Retrieval Math:** Implementing BM25, TF-IDF, and PageRank power iteration algorithms from scratch to understand how industry-standard search engines evaluate relevance and authority.
* **Real-World Scraping:** Dealing with actual internet friction, such as hidden Windows carriage returns (`\r\n`), Cloudflare rate-limiting, and parsing strict `robots.txt` guidelines.

## Technical Decision Reflection

### Why a Disk-Based Binary Index?
Initially, the index was loaded entirely into a Python dictionary. This caused the memory footprint to bloat to nearly 5x the file size. By converting the postings to a `.bin` file and using `seek()`, the engine achieved **~0.2 millisecond query times** while utilizing only a fraction of the RAM, satisfying strict O(log N) memory requirements.

### Why Target Liquipedia?
The original university project targeted isolated, static school servers. Adapting it to Rocket League Liquipedia solved a personal pain point: as a massive fan of RLCS, I wanted a lightning-fast way to look up player transfers, event brackets, and historical data without clicking through complex wiki menus.

Furthermore, hitting a live, modern wiki introduced real-world engineering complexities including dynamic routing, massive interconnected link graphs, and strict Cloudflare rate limits, making the final product much more robust. This genuine utility is exactly why I plan to augment the engine with Local AI (RAG) next, which will allow me to ask natural language questions and get synthesized answers instantly based on the scraped tournament data.

## Acknowledgments & Tools
* **CS 121 Project Team:** The foundational architecture and core algorithms adapted for this project were originally built in collaboration with my university groupmates: Cyril Joby, Pranav Sethia, and Rishi Murumkar.
* **AI Assistance:** Generative AI was used as a development tool during this solo adaptation to accelerate the creation of the Flask front-end UI boilerplate, troubleshoot complex debugging scenarios (like Windows carriage return parsing), and help format this documentation.

## Future Enhancement Plans
* **Local AI Augmentation (RAG):** Integrate a local LLM (via Ollama) to read the top K search results and generate a conversational, synthesized answer to the user's query directly on the search page.
* Spelling correction and fuzzy matching for queries.
* Frontend UI improvements (dark mode, expanded metadata snippets).

## License
MIT License - see LICENSE file for details

## Author
Neil Surya | [LinkedIn](https://www.linkedin.com/in/neilsurya) | [GitHub](https://github.com/neil-surya)