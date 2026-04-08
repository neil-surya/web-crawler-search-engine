import logging
from typing import Any, Optional
import requests


class Response:
    """Wrapper for HTTP responses to maintain compatibility with the crawler."""

    def __init__(self, url: str, status: int, error: str = "", raw_response: Optional[requests.Response] = None) -> None:
        """
        Initialize the custom response object.

        Args:
            url (str): The requested URL.
            status (int): HTTP status code (e.g., 200, 404).
            error (str, optional): Error message if the request failed. Defaults to "".
            raw_response (Optional[requests.Response], optional): The raw requests object. Defaults to None.
        """
        self.url: str = url
        self.status: int = status
        self.error: str = error
        self.raw_response: Optional[requests.Response] = raw_response


def download(url: str, config: Any, logger: Optional[logging.Logger] = None) -> Response:
    """
    Download a webpage from the live internet.

    Args:
        url (str): The URL to download.
        config (Any): Configuration object containing user agent and timeout settings.
        logger (Optional[logging.Logger], optional): Logger instance. Defaults to None.

    Returns:
        Response: A wrapped response object containing status and raw HTML.
    """
    # define headers to respectfully identify our crawler
    headers: dict[str, str] = {
        "User-Agent": getattr(config, "user_agent", "web-crawler-search-engine/1.0")
    }
    
    try:
        # fetch the webpage with a configured timeout
        resp: requests.Response = requests.get(
            url,
            headers=headers,
            timeout=getattr(config, "timeout", 10)
        )
        
        # return a successfully wrapped response
        return Response(
            url=url,
            status=resp.status_code,
            raw_response=resp
        )
        
    except requests.exceptions.RequestException as e:
        # log the error if a logger is provided
        if logger:
            logger.error(f"Failed to download {url}: {str(e)}")
            
        # return a failed response representation
        return Response(
            url=url,
            status=500, # use 500 for generic network failures
            error=str(e)
        )