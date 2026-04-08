import re
from urllib.parse import parse_qs, urldefrag, urljoin, urlparse
from bs4 import BeautifulSoup
from typing import Any

def scraper(url: str, resp: Any) -> list[str]:
    """
    Extract valid links from a downloaded webpage.

    Args:
        url (str): The URL of the downloaded page.
        resp (Any): The response object from the download.

    Returns:
        list[str]: A list of valid, filtered URLs found on the page.
    """
    # extract links from the response
    links: list[str] = extract_next_links(url, resp)
    
    # filter and return only valid links
    return [link for link in links if is_valid(link)]

def extract_next_links(url: str, resp: Any) -> list[str]:
    """
    Parse the HTML content and extract all raw links.

    Args:
        url (str): The base URL for resolving relative links.
        resp (Any): The response object containing HTML content.

    Returns:
        list[str]: A list of absolute, defragmented URLs.
    """
    links: list[str] = []
    
    # if the response failed or isn't HTML, return empty
    if resp is None or resp.status != 200 or resp.raw_response is None:
        return links

    c_type: str = (resp.raw_response.headers.get("Content-Type") or "").lower()
    if "text/html" not in c_type:
        return links

    # use html.parser as a safe, cross-platform default
    soup: BeautifulSoup = BeautifulSoup(resp.raw_response.content, "html.parser")

    # find all anchor tags with href attributes
    for a_tag in soup.find_all("a", href=True):
        raw: str = a_tag["href"].strip()
        
        # skip non-http schemas
        if raw.startswith(("mailto:", "javascript:", "tel:", "#")):
            continue
            
        try:
            # convert relative urls to absolute
            absolute_url: str = urljoin(resp.raw_response.url or url, raw)
        except ValueError:
            continue
        
        # remove fragment identifiers
        clean_url, _ = urldefrag(absolute_url)
        links.append(clean_url)

    return list(set(links))

def is_valid(url: str) -> bool:
    """
    Check if a URL belongs to allowed domains and is not a trap or file.

    Args:
        url (str): The URL to validate.

    Returns:
        bool: True if the URL is valid to crawl, False otherwise.
    """
    allowed_domains: tuple[str, ...] = (
        ".ics.uci.edu",
        ".cs.uci.edu",
        ".informatics.uci.edu",
        ".stat.uci.edu",
    )

    try:
        parsed = urlparse(url)
        
        # enforce http/https protocols
        if parsed.scheme not in {"http", "https"}:
            return False

        host: str = (parsed.hostname or "").lower()
        
        # reject urls with fragments
        if parsed.fragment:
            return False
            
        path_lower: str = parsed.path.lower()
        query_lower: str = parsed.query.lower()
        
        # trap filtering
        if (
            "timeline" in path_lower or "ml/datasets" in path_lower 
            or "/events/" in path_lower or "tribe" in path_lower 
            or "tribe" in query_lower or "wp-login" in path_lower 
            or "ical" in path_lower or "eppstein/pix" in path_lower 
            or "doku.php" in path_lower
            or re.search(r"/\d{4}/\d{2}/\d{2}", parsed.path)
            or re.search(r"/day/\d{4}-\d{2}-\d{2}", parsed.path)
            or re.search(r"/\d{4}-\d{2}$", parsed.path)
            or re.search(r"date=\d{4}-\d{2}-\d{2}", parsed.query)
        ):
            return False

        # block specific subdomains
        if host == "gitlab.ics.uci.edu":
            return False

        # ensure domain is in the allowed list
        if not any(host.endswith(domain) for domain in allowed_domains):
            return False

        # file extension filtering
        return not re.match(
            r".*\.(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1"
            + r"|thmx|mso|arff|rtf|jar|csv"
            + r"|war|java|bam|svg|ppsx|pps"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz)$",
            path_lower,
        )
    except TypeError:
        return False
