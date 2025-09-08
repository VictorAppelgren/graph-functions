"""
World-class Source Scraper for News Ingestion.

- Fast static (httpx+trafilatura) path
- Browser fallback (Playwright)
- Auto-login & cookies per domain
- Obsessive logging (console+file)
- Polite scraping (delays, real headers)
- Ultra-clean output (trafilatura)
- Recursive URL extraction for all sources
"""

import json
import random
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

import httpx
import trafilatura

from . import config
from utils import logging

logger = logging.get_logger(__name__)

USER_AGENT = config.USER_AGENT
MIN_WORDS_OK = 100

# --- Utility: get domain from URL ---
def domain_from_url(url: str) -> str:
    return urlparse(url).netloc.lstrip("www.")

# --- Utility: is article text good? ---
def is_article_good(text: str) -> bool:
    if not text:
        return False
    words = text.split()
    if len(words) < MIN_WORDS_OK:
        return False
    return True

# --- Utility: polite random delay ---
async def random_delay(min_s: float = 1.0, max_s: float = 2.5):
    await asyncio.sleep(random.uniform(min_s, max_s))

# --- Credential & cookie handling ---
def load_login(domain: str) -> Optional[dict]:
    if LOGIN_FILE.exists():
        try:
            data = json.loads(LOGIN_FILE.read_text())
            return data.get(domain)
        except Exception as e:
            logger.error(f"Could not parse {LOGIN_FILE}: {e}")
    return None

def cookie_file(domain: str) -> Path:
    return COOKIE_DIR / f"{domain}.json"

def load_cookies_from_disk(domain: str) -> Optional[list]:
    cf = cookie_file(domain)
    if cf.exists():
        try:
            return json.loads(cf.read_text())
        except json.JSONDecodeError:
            logger.warning(f"Cookie file {cf} is corrupted; ignoring")
    return None


# --- Static (httpx+trafilatura) fetch path ---
async def try_static_fetch(url: str, cookies: Optional[list] = None) -> str:
    logger.debug(f"[static] GET {url}")
    headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=20) as client:
        try:
            resp = await client.get(url, cookies={c["name"]: c["value"] for c in cookies or []})
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.debug(f"[static] HTTP error {e.response.status_code}")
            return ""
        except (httpx.TransportError, httpx.TimeoutException) as e:
            logger.debug(f"[static] transport error: {e}")
            return ""
    text = trafilatura.extract(resp.text) or ""
    logger.debug(f"[static] extracted {len(text)} chars")
    return text

# --- Playwright path ---
async def playwright_fetch(url: str, domain: str, cookies: Optional[list] = None, login_cfg: Optional[dict] = None) -> str:
    if async_playwright is None:
        logger.error("Playwright is not installed. Please install it with: pip install playwright")
        return ""
    logger.debug(f"[browser] Launch Chromium headless for {url}")
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context(user_agent=USER_AGENT)
    if cookies:
        try:
            await context.add_cookies(cookies)
        except Exception as e:
            logger.warning(f"Could not load cookies for {domain}: {e}")
    page = await context.new_page()
    try:
        await page.goto(url, wait_until="networkidle", timeout=20000)
        await random_delay()
        # If login config is present, try to log in
        if login_cfg:
            try:
                await page.goto(login_cfg.get("login_url", url), wait_until="networkidle", timeout=20000)
                await random_delay()
                await page.fill('input[type="email"],input[name*="user"]', login_cfg["username"])
                await page.fill('input[type="password"]', login_cfg["password"])
                await page.keyboard.press("Enter")
                await page.wait_for_load_state("networkidle", timeout=8000)
                await random_delay()
                await page.goto(url, wait_until="networkidle", timeout=20000)
            except Exception as e:
                logger.debug(f"Login automation failed for {domain}: {e}")
        html = await page.content()
        text = trafilatura.extract(html) or ""
        await save_cookies(context, domain)
        if is_article_good(text):
            logger.debug(f"Login+browser fetch succeeded ✅ ({len(text.split())} words)")
            return text
        else:
            logger.debug(f"Login+browser fetch failed to get good content for {url}")
    except Exception as e:
        logger.debug(f"Exception during login+fetch: {e}")
# --- Main orchestrator for a single URL ---
async def fetch_article(url: str) -> str:
    """
    Perform a single robust static scrape (httpx + trafilatura). No browser escalation.
    Returns article text or empty string if failed.
    """
    log_url = url if len(url) <= 80 else url[:77] + '...'
    headers = {"User-Agent": USER_AGENT}
    try:
        async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=20) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            text = trafilatura.extract(resp.text) or ""
            if text:
                logger.debug(f"Scrape succeeded ({len(text.split())} words)")
                sample = text[:400] + ("..." if len(text) > 400 else "")
                logger.debug(f"Sample: {sample}")
            else:
                logger.debug(f"Scrape returned no extractable text for {log_url}")
            return text
        
    except httpx.HTTPStatusError as e:
        logger.debug(f"HTTP error {e.response.status_code} for {log_url}")
    except (httpx.TransportError, httpx.TimeoutException) as e:
        logger.debug(f"Transport error for {log_url}: {e}")
    except Exception as e:
        logger.error(f"Failed to scrape {log_url}: {e}")
    return ""

# --- Recursive URL extraction utility (from find_articles_from_source.py) ---
def extract_all_urls(data) -> List[str]:
    """Recursively extract all string values that look like URLs from any dict/list."""
    urls = []
    if isinstance(data, dict):
        for k, v in data.items():
            if k.lower() == "url" and isinstance(v, str) and v.startswith("http"):
                urls.append(v)
            elif k.lower() == "links" and isinstance(v, list):
                urls.extend([item for item in v if isinstance(item, str) and item.startswith("http")])
            else:
                urls.extend(extract_all_urls(v))
    elif isinstance(data, list):
        for item in data:
            urls.extend(extract_all_urls(item))
    elif isinstance(data, str) and data.startswith("http"):
        urls.append(data)
    return list(set(urls))  # deduplicate

# --- Main interface: scrape_article_and_sources ---
async def scrape_article_and_sources(article_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Scrape ONLY linked/source URLs (not the main article).
    Adds a 'scraped_sources' field to the article_data dict:
        'scraped_sources': [ {'url': ..., 'text': ...}, ... ]
    Only sources that pass is_article_good are included.
    """
    if not article_data:
        raise ValueError("Article data cannot be None or empty")

    urls = extract_all_urls(article_data)
    if not urls:
        logger.debug("No URLs found to scrape in article_data")
        article_data["scraped_sources"] = []
        return article_data

    main_url = article_data.get("url") or urls[0]
    source_urls = [u for u in urls if u != main_url]

    scraped_sources = []
    import json
    for src_url in source_urls:
        # Always log a clear separator before every source
        logger.debug("---------------- NEW SOURCE -------------------------------")
        src_url_sample = src_url if len(src_url) <= 80 else src_url[:77] + '...'
        logger.debug(f"Scraping source: {src_url_sample}")
        text = await fetch_article(src_url)
        if is_article_good(text):
            json_len_before = len(json.dumps(article_data))
            scraped_sources.append({"url": src_url, "text": text})
            article_data["scraped_sources"] = scraped_sources
            json_len_after = len(json.dumps(article_data))
            logger.debug(f"JSON length before adding source: {json_len_before}, after: {json_len_after}")
            logger.debug("✅ Source passed QA check.")
        else:
            logger.debug("❌ Source failed QA and will be excluded.")
        
    logger.debug("---------------- END SOURCE INTERATION ----------------------")

    article_data = dict(article_data)
    article_data["scraped_sources"] = scraped_sources
    return article_data

# --- Synchronous wrapper ---
def scrape_article_and_sources_sync(article_data: Dict[str, Any]) -> Dict[str, Any]:
    return asyncio.run(scrape_article_and_sources(article_data))