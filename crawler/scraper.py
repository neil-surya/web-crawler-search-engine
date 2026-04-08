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
    
    # if the response failed or isn't html, return empty
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
    Check if a URL belongs to Liquipedia Rocket League and is not a trap.

    Args:
        url (str): The URL to validate.

    Returns:
        bool: True if the URL is valid to crawl, False otherwise.
    """
    try:
        parsed = urlparse(url)
        
        # enforce http/https protocols
        if parsed.scheme not in {"http", "https"}:
            return False

        host: str = (parsed.hostname or "").lower()
        
        # must be liquipedia
        if host not in {"liquipedia.net", "www.liquipedia.net"}:
            return False

        path: str = parsed.path
        
        # must stay within the rocket league wiki to avoid other esports
        if not path.startswith("/rocketleague/"):
            return False

        # reject urls with fragments
        if parsed.fragment:
            return False
            
        # block special, user, and talk namespaces
        if any(namespace in path for namespace in [
            "/Special:", 
            "/User:", 
            "/User_talk:", 
            "/Talk:",
            "/Template:",
            "/Template_talk:",
            "/Category_talk:"
        ]):
            return False

        # block query parameters that create infinite loops
        query: str = parsed.query.lower()
        if any(trap in query for trap in [
            "action=",
            "oldid=",
            "diff=",
            "dir=",
            "limit=",
            "printable="
        ]):
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
            path.lower(),
        )
    except TypeError:
        return False
