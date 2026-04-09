import array
import json
import math
import re
import struct
from typing import Any, Optional

from utils.text_processing import tokenize

# bm25 length normalization strength
BM25_B: float = 0.75


class SearchEngine:
    """Core retrieval engine utilizing BM25, PageRank, and disk-based binary lookups."""

    def __init__(self, index_dir: str = "data/index") -> None:
        """
        Initialize the search engine and load lightweight offset maps into memory.

        Args:
            index_dir (str): Directory containing the optimized binary index files.
        """
        self.index_dir: str = index_dir
        self.tokens_bytes: bytes = b""
        self.tokens_offsets: array.array = array.array("I")
        self.offset_vals: array.array = array.array("Q")
        self.length_vals: array.array = array.array("I")
        
        self.doc_map: dict[str, str] = {}
        self.doc_lengths: dict[str, int] = {}
        self.pr_scores: dict[str, float] = {}
        self.avg_len: float = 1.0
        self.n_docs: int = 0
        
        # open file handle for seeking disk postings
        self.postings_fh: Any = None
        
        self._load_index()

    def _load_tokens_compact(self, path: str) -> tuple[bytes, array.array]:
        """
        Load tokens as a single bytes object and an array of line-start offsets.
        Keeps memory footprint incredibly small.
        """
        with open(path, "rb") as f:
            data: bytes = f.read()
            
        parts: list[bytes] = data.split(b"\n")
        if parts and not parts[-1]:
            parts.pop()
            
        offsets: array.array = array.array("I")
        pos: int = 0
        for p in parts:
            offsets.append(pos)
            pos += len(p) + 1  # account for newline
            
        return data, offsets

    def _load_index(self) -> None:
        """Load the lightweight offset index and doc metadata into memory."""
        print("Loading lightweight index into memory...")
        
        # load compact lexicon
        tokens_path: str = f"{self.index_dir}/tokens.txt"
        self.tokens_bytes, self.tokens_offsets = self._load_tokens_compact(tokens_path)
        
        # load binary offsets array
        with open(f"{self.index_dir}/offsets_compact.bin", "rb") as f:
            n: int = struct.unpack("I", f.read(4))[0]
            self.offset_vals.fromfile(f, n)
            self.length_vals.fromfile(f, n)
            
        # load metadata
        with open(f"{self.index_dir}/doc_map.json", "r", encoding="utf-8") as f:
            self.doc_map = json.load(f)
            self.n_docs = len(self.doc_map)
            
        with open(f"{self.index_dir}/doc_lengths.json", "r", encoding="utf-8") as f:
            self.doc_lengths = json.load(f)
            
        # calculate bm25 average document length
        if self.n_docs > 0:
            self.avg_len = sum(self.doc_lengths.values()) / self.n_docs
            
        # load optional pagerank scores
        try:
            with open(f"{self.index_dir}/pagerank.json", "r", encoding="utf-8") as f:
                self.pr_scores = json.load(f)
        except FileNotFoundError:
            pass
            
        # keep postings file open for seeking during queries
        self.postings_fh = open(f"{self.index_dir}/postings.bin", "rb")
        
        print(f"Engine Ready: {n:,} unique tokens, {self.n_docs:,} documents.")

    def _bisect_tokens(self, term: str) -> int:
        """Binary search for a term in the compact bytes buffer."""
        term_b: bytes = term.encode("utf-8")
        n: int = len(self.tokens_offsets)
        lo: int = 0
        hi: int = n - 1
        
        while lo <= hi:
            mid: int = (lo + hi) // 2
            start: int = self.tokens_offsets[mid]
            end: int = self.tokens_offsets[mid + 1] - 1 if mid + 1 < n else len(self.tokens_bytes)
            
            token: bytes = self.tokens_bytes[start:end]
            
            # FIX: Strip the hidden carriage return
            if token.endswith(b"\r"):
                token = token[:-1]
            
            if token == term_b:
                return mid
            elif token < term_b:
                lo = mid + 1
            else:
                hi = mid - 1
                
        return -1

    def _read_postings(self, term: str) -> Optional[list[list[int]]]:
        """Locate term via binary search, then seek to its posting list on disk."""
        i: int = self._bisect_tokens(term)
        if i < 0:
            return None
            
        offset: int = self.offset_vals[i]
        length: int = self.length_vals[i]
        
        self.postings_fh.seek(offset)
        data: bytes = self.postings_fh.read(length)
        return json.loads(data)

    def search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        """Score documents using BM25, importance boost, bigram bonus, and PageRank."""
        # tokenize query, removing stopwords
        raw_terms: list[str] = tokenize(query, apply_stemming=True, filter_stopwords=True)
        
        # fallback: if all words were stopwords (e.g. "how to"), keep them
        if not raw_terms:
            raw_terms = tokenize(query, apply_stemming=True, filter_stopwords=False)
            if not raw_terms:
                return []

        # deduplicate while preserving order
        query_terms: list[str] = list(dict.fromkeys(raw_terms))
        
        # boolean AND: fetch posting lists; fail early if any term is missing
        posting_lists: list[list[list[int]]] = []
        for term in query_terms:
            postings = self._read_postings(term)
            if postings is None:
                return []
            posting_lists.append(postings)

        # intersect to find documents containing all terms
        common_docs: set[int] = set(p[0] for p in posting_lists[0])
        for pl in posting_lists[1:]:
            common_docs &= set(p[0] for p in pl)
            
        if not common_docs:
            return []

        scores: dict[int, float] = {}
        
        # layer 1: bm25 tf-idf + importance boost
        for term, postings in zip(query_terms, posting_lists):
            df: int = len(postings)
            idf: float = math.log10(self.n_docs / df) if df else 0.0
            
            for doc_id, tf, important in postings:
                if doc_id not in common_docs:
                    continue
                    
                doc_len: int = self.doc_lengths.get(str(doc_id), self.avg_len)
                tf_norm: float = tf / (1.0 - BM25_B + BM25_B * doc_len / self.avg_len)
                tf_log: float = 1.0 + math.log10(tf_norm) if tf_norm > 0 else 0.0
                
                # double weight for title/heading terms
                boost: float = 2.0 if important else 1.0 
                scores[doc_id] = scores.get(doc_id, 0.0) + (tf_log * idf * boost)

        # layer 2: bigram bonus
        if len(query_terms) > 1:
            for i in range(len(query_terms) - 1):
                bigram: str = f"{query_terms[i]} {query_terms[i+1]}"
                bi_postings = self._read_postings(bigram)
                
                if bi_postings:
                    df: int = len(bi_postings)
                    idf: float = math.log10(self.n_docs / df)
                    for doc_id, tf, _ in bi_postings:
                        if doc_id in common_docs:
                            tf_log: float = 1.0 + math.log10(tf) if tf > 0 else 0.0
                            scores[doc_id] += (tf_log * idf * 1.5)

        # layer 3: pagerank multiplicative boost
        if self.pr_scores:
            for doc_id in scores:
                pr: float = self.pr_scores.get(str(doc_id), 0.0)
                scores[doc_id] *= (1.0 + 0.5 * pr)

        # layer 4: sort and format
        ranked: list[tuple[int, float]] = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        seen_base: set[str] = set()
        results: list[tuple[str, float]] = []
        
        for doc_id, score in ranked:
            url: str = self.doc_map[str(doc_id)]
            # normalize to avoid identical result pages
            base_url: str = re.sub(r'/index\.[a-zA-Z]+$', '/', url.split("#")[0]).rstrip('/')
            
            if base_url not in seen_base:
                seen_base.add(base_url)
                results.append((url, score))
                
            if len(results) == top_k:
                break
                
        return results

    def close(self) -> None:
        """Safely close the file handle."""
        if self.postings_fh:
            self.postings_fh.close()
