"""
Shared text processing utilities for the web crawler and search engine.
"""

import re
import hashlib
from nltk.stem import PorterStemmer

# initialize stemmer once to avoid repeated construction overhead
stemmer: PorterStemmer = PorterStemmer()

STOP_WORDS: set[str] = {
    'a', 'about', 'above', 'after', 'again', 'against', 'all', 'am', 'an', 'and',
    'any', 'are', "aren't", 'as', 'at', 'be', 'because', 'been', 'before', 'being',
    'below', 'between', 'both', 'but', 'by', "can't", 'cannot', 'could', "couldn't",
    'did', "didn't", 'do', 'does', "doesn't", 'doing', "don't", 'down', 'during',
    'each', 'few', 'for', 'from', 'further', 'had', "hadn't", 'has', "hasn't",
    'have', "haven't", 'having', 'he', "he'd", "he'll", "he's", 'her', 'here',
    "here's", 'hers', 'herself', 'him', 'himself', 'his', 'how', "how's", 'i',
    "i'd", "i'll", "i'm", "i've", 'if', 'in', 'into', 'is', "isn't", 'it', "it's",
    'its', 'itself', "let's", 'me', 'more', 'most', "mustn't", 'my', 'myself',
    'no', 'nor', 'not', 'of', 'off', 'on', 'once', 'only', 'or', 'other', 'ought',
    'our', 'ours', 'ourselves', 'out', 'over', 'own', 'same', "shan't", 'she',
    "she'd", "she'll", "she's", 'should', "shouldn't", 'so', 'some', 'such', 'than',
    'that', "that's", 'the', 'their', 'theirs', 'them', 'themselves', 'then',
    'there', "there's", 'these', 'they', "they'd", "they'll", "they're", "they've",
    'this', 'those', 'through', 'to', 'too', 'under', 'until', 'up', 'very', 'was',
    "wasn't", 'we', "we'd", "we'll", "we're", "we've", 'were', "weren't", 'what',
    "what's", 'when', "when's", 'where', "where's", 'which', 'while', 'who',
    "who's", 'whom', 'why', "why's", 'with', "won't", 'would', "wouldn't", 'you',
    "you'd", "you'll", "you're", "you've", 'your', 'yours', 'yourself', 'yourselves'
}

# SimHash config
SIMHASH_BITS: int = 64
BAND_SIZE: int = 16
NUM_BANDS: int = SIMHASH_BITS // BAND_SIZE
NEAR_DUP_THRESHOLD: int = 3
BAND_MASK: int = (1 << BAND_SIZE) - 1


def tokenize(text: str, apply_stemming: bool = True, filter_stopwords: bool = False) -> list[str]:
    """
    Convert raw text into normalized tokens.

    Args:
        text (str): Input text.
        apply_stemming (bool): Whether to apply stemming.
        filter_stopwords (bool): Whether to remove stopwords.

    Returns:
        list[str]: Processed tokens.
    """
    # extract alphanumeric tokens
    tokens: list[str] = re.findall(r"[a-zA-Z0-9]+", text)

    # normalize to lowercase
    tokens = [t.lower() for t in tokens]

    # optionally remove stopwords
    if filter_stopwords:
        tokens = [t for t in tokens if t not in STOP_WORDS]

    # optionally apply stemming
    if apply_stemming:
        tokens = [stemmer.stem(t) for t in tokens]

    return tokens


def generate_simhash(tokens: list[str]) -> int:
    """
    Generate a 64-bit SimHash fingerprint for a list of tokens.

    Args:
        tokens (list[str]): Input tokens.

    Returns:
        int: SimHash fingerprint.
    """
    v: list[int] = [0] * SIMHASH_BITS

    for token in tokens:
        h: int = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
        h &= (1 << SIMHASH_BITS) - 1  # limit to SIMHASH_BITS

        for i in range(SIMHASH_BITS):
            v[i] += 1 if (h >> i) & 1 else -1

    fp: int = 0
    for i in range(SIMHASH_BITS):
        if v[i] > 0:
            fp |= (1 << i)

    return fp


def get_simhash_bands(fp: int) -> list[int]:
    """
    Split a SimHash fingerprint into LSH bands.

    Args:
        fp (int): SimHash fingerprint.

    Returns:
        list[int]: List of band values.
    """
    return [(fp >> (i * BAND_SIZE)) & BAND_MASK for i in range(NUM_BANDS)]


def is_near_duplicate(fp: int, bands_table: list[dict[int, list[int]]]) -> bool:
    """
    Check if a fingerprint is near-duplicate using LSH banding.

    Args:
        fp (int): Fingerprint to check.
        bands_table (list[dict[int, list[int]]]): LSH bands table.

    Returns:
        bool: True if near-duplicate exists.
    """
    candidates: set[int] = set()

    # collect candidates from matching bands
    for i, band_val in enumerate(get_simhash_bands(fp)):
        candidates.update(bands_table[i].get(band_val, []))

    # compute hamming distance
    return any(bin(fp ^ c).count("1") <= NEAR_DUP_THRESHOLD for c in candidates)


def add_to_bands(fp: int, bands_table: list[dict[int, list[int]]]) -> None:
    """
    Add a fingerprint to the LSH bands table.

    Args:
        fp (int): Fingerprint to add.
        bands_table (list[dict[int, list[int]]]): LSH bands table.
    """
    for i, band_val in enumerate(get_simhash_bands(fp)):
        bands_table[i].setdefault(band_val, []).append(fp)
