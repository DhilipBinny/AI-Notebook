"""
Web Tools - Allows LLM to fetch and read web content.

These tools help the LLM:
- Fetch documentation pages and convert to readable format
- Get library documentation for helping users
- Read web content that users reference
"""

import re
from typing import Optional
from backend.utils.util_func import log_debug_message

# Try to import optional dependencies
try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

try:
    import html2text
    HAS_HTML2TEXT = True
except ImportError:
    HAS_HTML2TEXT = False


def _html_to_markdown(html: str) -> str:
    """Convert HTML to markdown."""
    if HAS_HTML2TEXT:
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True
        h.ignore_tables = False
        h.body_width = 0  # Don't wrap lines
        return h.handle(html)
    else:
        # Basic fallback - strip HTML tags
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()


def _clean_markdown(text: str) -> str:
    """Clean up markdown text - remove excessive whitespace, comments, etc."""
    # Remove HTML comments
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    # Remove excessive blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Remove leading/trailing whitespace per line
    lines = [line.strip() for line in text.split('\n')]
    return '\n'.join(lines).strip()


def fetch_url_as_markdown(url: str, max_length: int = 15000) -> dict:
    """
    Fetch a web page and convert it to markdown for easy reading.

    WHEN TO USE THIS TOOL:
    - User shares a URL and asks "look at this" or "help me with this page"
    - User asks about documentation from a specific URL
    - Need to read external content to help user

    WHEN NOT TO USE THIS TOOL:
    - For library documentation → use get_library_docs(library_name) instead
    - For files in project → use read_text_file()

    Args:
        url: The URL to fetch
        max_length: Maximum characters to return (default: 15000)

    Returns:
        Dictionary with:
        - success: Whether fetch succeeded
        - url: The URL fetched
        - title: Page title if found
        - content: Markdown content (may be truncated)
        - length: Length of content
        - truncated: Whether content was truncated
        - error: Error message if failed

    Example:
        fetch_url_as_markdown("https://pandas.pydata.org/docs/getting_started/")
    """
    log_debug_message(f"==> fetch_url_as_markdown({url}) called from LLM")

    if not HAS_HTTPX:
        return {
            "success": False,
            "url": url,
            "error": "httpx library not installed. Cannot fetch URLs."
        }

    # Validate URL
    if not url.startswith(('http://', 'https://')):
        return {
            "success": False,
            "url": url,
            "error": "Invalid URL. Must start with http:// or https://"
        }

    try:
        # Fetch the page
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; NotebookAssistant/1.0)"
        }

        with httpx.Client(timeout=15, follow_redirects=True) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()

        content_type = response.headers.get('content-type', '')

        # Handle different content types
        if 'text/html' in content_type:
            html = response.text

            # Try to extract title
            title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
            title = title_match.group(1).strip() if title_match else None

            # Convert to markdown
            markdown = _html_to_markdown(html)
            markdown = _clean_markdown(markdown)

        elif 'text/plain' in content_type or 'text/markdown' in content_type:
            markdown = response.text
            title = None

        elif 'application/json' in content_type:
            import json
            markdown = f"```json\n{json.dumps(response.json(), indent=2)}\n```"
            title = "JSON Response"

        else:
            return {
                "success": False,
                "url": url,
                "error": f"Unsupported content type: {content_type}"
            }

        # Truncate if needed
        truncated = len(markdown) > max_length
        if truncated:
            markdown = markdown[:max_length] + "\n\n... (content truncated)"

        return {
            "success": True,
            "url": url,
            "title": title,
            "content": markdown,
            "length": len(markdown),
            "truncated": truncated
        }

    except httpx.TimeoutException:
        return {
            "success": False,
            "url": url,
            "error": "Request timed out"
        }
    except httpx.HTTPStatusError as e:
        return {
            "success": False,
            "url": url,
            "error": f"HTTP error {e.response.status_code}"
        }
    except Exception as e:
        return {
            "success": False,
            "url": url,
            "error": f"Failed to fetch URL: {str(e)}"
        }


def get_library_docs(library_name: str, topic: Optional[str] = None) -> dict:
    """
    Get documentation for a Python library to help answer user questions.

    WHEN TO USE THIS TOOL:
    - User asks "how do I use pandas?"
    - User asks about a specific function: "how does matplotlib.pyplot.scatter work?"
    - Need to look up library API to help user

    WHEN NOT TO USE THIS TOOL:
    - User provides a specific URL → use fetch_url_as_markdown(url) instead
    - For general Python questions → use your training knowledge

    Args:
        library_name: Name of the Python library (e.g., "pandas", "numpy", "matplotlib")
        topic: Optional specific topic or function (e.g., "DataFrame", "scatter", "groupby")

    Returns:
        Dictionary with:
        - success: Whether docs were found
        - library: Library name
        - topic: Topic searched for
        - source: Where docs came from
        - content: Documentation content
        - url: URL of documentation
        - error: Error message if failed

    Example:
        get_library_docs("pandas")  → general pandas docs
        get_library_docs("pandas", "DataFrame.groupby")  → specific function docs
        get_library_docs("matplotlib", "scatter")  → matplotlib scatter docs
    """
    log_debug_message(f"==> get_library_docs({library_name}, topic={topic}) called from LLM")

    if not HAS_HTTPX:
        return {
            "success": False,
            "library": library_name,
            "error": "httpx library not installed. Cannot fetch documentation."
        }

    # Known documentation URLs for popular libraries
    DOCS_URLS = {
        "pandas": "https://pandas.pydata.org/docs/",
        "numpy": "https://numpy.org/doc/stable/",
        "matplotlib": "https://matplotlib.org/stable/",
        "seaborn": "https://seaborn.pydata.org/",
        "scikit-learn": "https://scikit-learn.org/stable/",
        "sklearn": "https://scikit-learn.org/stable/",
        "scipy": "https://docs.scipy.org/doc/scipy/",
        "tensorflow": "https://www.tensorflow.org/api_docs/python/",
        "torch": "https://pytorch.org/docs/stable/",
        "pytorch": "https://pytorch.org/docs/stable/",
        "requests": "https://requests.readthedocs.io/en/latest/",
        "flask": "https://flask.palletsprojects.com/",
        "django": "https://docs.djangoproject.com/en/stable/",
        "fastapi": "https://fastapi.tiangolo.com/",
        "sqlalchemy": "https://docs.sqlalchemy.org/",
        "plotly": "https://plotly.com/python/",
        "bokeh": "https://docs.bokeh.org/en/latest/",
        "pillow": "https://pillow.readthedocs.io/en/stable/",
        "pil": "https://pillow.readthedocs.io/en/stable/",
        "opencv": "https://docs.opencv.org/4.x/d6/d00/tutorial_py_root.html",
        "cv2": "https://docs.opencv.org/4.x/d6/d00/tutorial_py_root.html",
    }

    library_lower = library_name.lower().strip()

    # Check if we know this library
    if library_lower not in DOCS_URLS:
        # Try PyPI for unknown libraries
        pypi_url = f"https://pypi.org/project/{library_name}/"
        result = fetch_url_as_markdown(pypi_url, max_length=10000)

        if result["success"]:
            return {
                "success": True,
                "library": library_name,
                "topic": topic,
                "source": "pypi",
                "content": result["content"],
                "url": pypi_url,
                "note": "Documentation from PyPI. For detailed API docs, check the library's official documentation."
            }
        else:
            return {
                "success": False,
                "library": library_name,
                "topic": topic,
                "error": f"Unknown library '{library_name}'. Could not find documentation."
            }

    base_url = DOCS_URLS[library_lower]

    # Build search URL based on library and topic
    if topic:
        # Try to construct a search or specific page URL
        search_urls = []

        # Common documentation URL patterns
        if library_lower in ["pandas", "numpy", "scipy"]:
            search_urls.append(f"{base_url}reference/api/{library_lower}.{topic}.html")
            search_urls.append(f"{base_url}search.html?q={topic}")
        elif library_lower in ["matplotlib"]:
            search_urls.append(f"{base_url}api/_as_gen/matplotlib.pyplot.{topic}.html")
            search_urls.append(f"{base_url}search.html?q={topic}")
        elif library_lower in ["sklearn", "scikit-learn"]:
            search_urls.append(f"{base_url}modules/generated/sklearn.{topic}.html")
            search_urls.append(f"{base_url}search.html?q={topic}")
        else:
            search_urls.append(f"{base_url}search.html?q={topic}")
            search_urls.append(f"{base_url}?q={topic}")

        # Try each URL
        for url in search_urls:
            result = fetch_url_as_markdown(url, max_length=12000)
            if result["success"] and len(result.get("content", "")) > 500:
                return {
                    "success": True,
                    "library": library_name,
                    "topic": topic,
                    "source": "official_docs",
                    "content": result["content"],
                    "url": url
                }

        # Fallback to base docs with note about topic
        result = fetch_url_as_markdown(base_url, max_length=10000)
        if result["success"]:
            return {
                "success": True,
                "library": library_name,
                "topic": topic,
                "source": "official_docs",
                "content": result["content"],
                "url": base_url,
                "note": f"Could not find specific docs for '{topic}'. Showing main documentation page."
            }

    else:
        # Get main documentation page
        result = fetch_url_as_markdown(base_url, max_length=12000)

        if result["success"]:
            return {
                "success": True,
                "library": library_name,
                "topic": None,
                "source": "official_docs",
                "content": result["content"],
                "url": base_url
            }

    return {
        "success": False,
        "library": library_name,
        "topic": topic,
        "error": "Failed to fetch library documentation"
    }
