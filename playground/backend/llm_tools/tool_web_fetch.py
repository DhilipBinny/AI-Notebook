"""
Web Fetch Tool - Allows LLM to fetch and read web content.

Downloads web pages, API responses, and files. Converts HTML to clean
readable text using BeautifulSoup. Inspired by OpenClaw's web_fetch tool
and toolslm's read_html/html2md.
"""

import os
import re
import httpx
from pathlib import Path
from typing import Optional
from backend.utils.util_func import log


# Limits
MAX_RESPONSE_BYTES = 512 * 1024  # 512KB max download
MAX_OUTPUT_CHARS = 50_000  # 50K chars max returned to LLM
REQUEST_TIMEOUT = 30  # seconds

# Workspace for saving downloaded files
WORKSPACE_DIR = Path(os.environ.get("WORKSPACE_PATH", "/workspace"))


def _html_to_text(html: str) -> str:
    """Convert HTML to clean readable text using BeautifulSoup."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        # Fallback: strip tags with regex
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    soup = BeautifulSoup(html, 'html.parser')

    # Remove non-content elements
    for tag in soup.find_all(['script', 'style', 'nav', 'footer', 'header',
                               'noscript', 'iframe', 'svg']):
        tag.decompose()

    # Try to find main content area first
    main = (soup.find('main')
            or soup.find('article')
            or soup.find(role='main')
            or soup.find(id=re.compile(r'content|main|article', re.I))
            or soup.find(class_=re.compile(r'content|main|article', re.I)))

    target = main if main else soup.body if soup.body else soup

    # Extract text with basic structure
    lines = []
    for element in target.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                                     'p', 'li', 'td', 'th', 'pre', 'code',
                                     'blockquote', 'div']):
        text = element.get_text(separator=' ', strip=True)
        if not text:
            continue

        tag = element.name
        if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            level = int(tag[1])
            lines.append(f"\n{'#' * level} {text}\n")
        elif tag == 'li':
            lines.append(f"- {text}")
        elif tag in ('pre', 'code'):
            if len(text) > 40:
                lines.append(f"```\n{text}\n```")
            else:
                lines.append(f"`{text}`")
        elif tag == 'blockquote':
            lines.append(f"> {text}")
        else:
            lines.append(text)

    result = '\n'.join(lines)
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result.strip()


def web_fetch(url: str, save_as: Optional[str] = None) -> dict:
    """
    Fetch content from a URL. For HTML pages, converts to clean readable text.
    For other content types (JSON, CSV, plain text), returns raw content.
    Optionally saves the response to a file in the workspace.

    Use this tool when you need to:
    - Download a dataset or CSV from a URL
    - Read documentation or web pages
    - Fetch API responses (JSON endpoints)
    - Download files into the workspace for processing
    - Check if a URL is accessible

    Args:
        url: The URL to fetch (must start with http:// or https://)
        save_as: Optional filename to save the response to in the workspace
                 (e.g., "data.csv", "response.json"). If not provided, content
                 is returned as text only.

    Returns:
        Dictionary with:
        - success: Whether the fetch succeeded
        - url: The requested URL
        - content: The fetched content (HTML converted to text, or raw content)
        - content_type: The response content type
        - status_code: HTTP status code
        - size_bytes: Size of the response
        - saved_to: Path where file was saved (if save_as was provided)
        - truncated: Whether content was truncated
        - error: Error message if fetch failed

    Example:
        To read docs: web_fetch("https://docs.python.org/3/library/json.html")
        To download CSV: web_fetch("https://example.com/data.csv", save_as="data.csv")
        To fetch API: web_fetch("https://api.github.com/repos/python/cpython")
    """
    log(f"==> web_fetch({url}) called from LLM")

    if not url or not url.strip():
        return {
            "success": False,
            "error": "No URL provided"
        }

    url = url.strip()
    if not url.startswith(('http://', 'https://')):
        return {
            "success": False,
            "error": "URL must start with http:// or https://"
        }

    try:
        with httpx.Client(
            timeout=REQUEST_TIMEOUT,
            follow_redirects=True,
            max_redirects=5
        ) as client:
            response = client.get(
                url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (compatible; AINotebook/1.0)',
                    'Accept': 'text/html,application/xhtml+xml,application/json,text/plain,*/*',
                }
            )

        status_code = response.status_code
        content_type = response.headers.get('content-type', '')
        raw_bytes = response.content
        size_bytes = len(raw_bytes)

        if size_bytes > MAX_RESPONSE_BYTES:
            raw_bytes = raw_bytes[:MAX_RESPONSE_BYTES]

        is_html = 'text/html' in content_type or 'application/xhtml' in content_type

        encoding = response.encoding or 'utf-8'
        try:
            text_content = raw_bytes.decode(encoding, errors='replace')
        except (LookupError, UnicodeDecodeError):
            text_content = raw_bytes.decode('utf-8', errors='replace')

        if is_html:
            text_content = _html_to_text(text_content)

        truncated = False
        if len(text_content) > MAX_OUTPUT_CHARS:
            text_content = text_content[:MAX_OUTPUT_CHARS]
            text_content += f"\n\n[Content truncated at {MAX_OUTPUT_CHARS} characters. Total size: {size_bytes} bytes]"
            truncated = True

        saved_to = None
        if save_as:
            WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
            save_path = (WORKSPACE_DIR / save_as).resolve()
            try:
                save_path.relative_to(WORKSPACE_DIR.resolve())
            except ValueError:
                return {
                    "success": False,
                    "error": f"Save path '{save_as}' is outside the workspace directory"
                }
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, 'wb') as f:
                f.write(response.content[:MAX_RESPONSE_BYTES])
            saved_to = str(save_path)

        return {
            "success": status_code < 400,
            "url": url,
            "content": text_content,
            "content_type": content_type.split(';')[0].strip(),
            "status_code": status_code,
            "size_bytes": size_bytes,
            "saved_to": saved_to,
            "truncated": truncated,
            "error": None if status_code < 400 else f"HTTP {status_code}"
        }

    except httpx.TimeoutException:
        return {
            "success": False,
            "error": f"Request timed out after {REQUEST_TIMEOUT} seconds"
        }
    except httpx.TooManyRedirects:
        return {
            "success": False,
            "error": "Too many redirects (limit: 5)"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to fetch URL: {str(e)}"
        }
