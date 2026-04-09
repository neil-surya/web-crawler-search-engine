import os
import json
import struct
import array
import logging
from typing import Any

# configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger: logging.Logger = logging.getLogger(__name__)


def build_doc_lengths(index: dict[str, list[dict[str, Any]]]) -> dict[int, int]:
    """
    Sum tf across all unigram terms per document to calculate document length.
    
    Args:
        index (dict[str, list[dict[str, Any]]]): Master inverted index.
        
    Returns:
        dict[int, int]: Mapping of document IDs to their total unigram lengths.
    """
    lengths: dict[int, int] = {}
    for token, postings in index.items():
        # skip bigrams (they contain a space) to avoid inflating denominators
        if " " in token:
            continue
            
        for p in postings:
            doc_id: int = p["doc_id"]
            lengths[doc_id] = lengths.get(doc_id, 0) + p["tf"]
            
    return lengths


def optimize_index() -> None:
    """
    Convert the master JSON index into a disk-friendly binary format.
    """
    logger.info("Loading master index...")
    try:
        with open("data/index/index.json", "r", encoding="utf-8") as f:
            index: dict[str, list[dict[str, Any]]] = json.load(f)
    except FileNotFoundError:
        logger.error("index.json not found. Run the indexer first.")
        return

    logger.info(f"Loaded {len(index):,} unique tokens.")

    # precompute document lengths for bm25 normalization
    logger.info("Computing document lengths...")
    doc_lengths: dict[int, int] = build_doc_lengths(index)
    
    with open("data/index/doc_lengths.json", "w", encoding="utf-8") as f:
        json.dump(doc_lengths, f)

    # process and pack postings
    logger.info("Writing binary postings and tracking offsets...")
    offsets: dict[str, list[int]] = {}
    
    with open("data/index/postings.bin", "wb") as f_postings:
        for token in sorted(index.keys()):
            # convert to compact triples: [doc_id, tf, important_flag]
            postings: list[dict[str, Any]] = index[token]
            compact: list[list[int]] = [
                [p["doc_id"], p["tf"], 1 if p.get("important") else 0] 
                for p in postings
            ]
            
            # serialize as tight json string without spaces
            line: bytes = json.dumps(compact, separators=(",", ":")).encode("utf-8") + b"\n"
            
            # record byte offset and length
            offset: int = f_postings.tell()
            f_postings.write(line)
            offsets[token] = [offset, len(line)]

    # write json offsets (used mostly for debugging/verification)
    with open("data/index/offsets.json", "w", encoding="utf-8") as f:
        json.dump(offsets, f)

    # write compact binary lexicon for high-speed binary search
    logger.info("Writing compact binary lexicon...")
    sorted_tokens: list[str] = sorted(offsets.keys())
    
    # 8-byte uint64 for byte offsets, 4-byte uint32 for lengths
    offset_vals: array.array = array.array("Q", (offsets[t][0] for t in sorted_tokens))
    length_vals: array.array = array.array("I", (offsets[t][1] for t in sorted_tokens))
    
    with open("data/index/tokens.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(sorted_tokens))
        
    n_tokens: int = len(sorted_tokens)
    with open("data/index/offsets_compact.bin", "wb") as f_bin:
        f_bin.write(struct.pack("I", n_tokens))
        offset_vals.tofile(f_bin)
        length_vals.tofile(f_bin)

    # report final sizes
    logger.info("Optimization complete. Index sizes:")
    for name in ["offsets.json", "postings.bin", "doc_lengths.json", "tokens.txt", "offsets_compact.bin"]:
        path: str = os.path.join("data/index", name)
        if os.path.exists(path):
            size_mb: float = os.path.getsize(path) / 1e6
            logger.info(f"  {name}: {size_mb:.1f} MB")
