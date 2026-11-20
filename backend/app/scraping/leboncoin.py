"""Leboncoin collection through the public r.jina.ai reader.

No DataDome bypass is attempted: the reader fetches the page server-side and
returns the full HTML (including the Next.js ``__NEXT_DATA__`` payload).
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Optional

from curl_cffi import requests

from ..config import JINA_HEADERS, JINA_READER, LEBONCOIN_BASE_URL, PROXY_URL, REQUEST_TIMEOUT, SCRAPE_STRATEGIES, USER_AGENT

NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)
BLOCK_MARKERS = (
    "captcha-delivery",
    "geo.captcha-delivery",
    "requiring captcha",
    "maybe requiring captcha",
    "access denied",
    "vous avez été bloqué",
)
READER_MARKDOWN_HEADERS = {"Accept": "*/*"}


class ScrapeError(RuntimeError):
    pass


@dataclass
class ScrapePage:
    ads: list[dict[str, Any]] = field(default_factory=list)
    total: Optional[int] = None
    blocked: bool = False
    error: Optional[str] = None
    strategy: str = ""


CATEGORY_IDS = {
    "informatique": "15",
    "ordinateurs": "15",
    "informatique/ordinateurs": "15",
    "pc": "15",
}


def normalize_category(value: Any) -> str:
    """Leboncoin's search route only accepts numeric category ids.

    A human label such as ``informatique/ordinateurs`` makes the reader return
    a challenge page, so unknown labels are dropped instead of sent.
    """
    text = str(value or "").strip()
    if not text:
        return ""
    if text.isdigit():
        return text
    return CATEGORY_IDS.get(text.lower().rstrip("/"), "")


def build_url(text: str, page: int = 1, category: str = "", price_min=None, price_max=None) -> str:
    params: dict[str, str] = {
        "text": text,
        "sort": "time",
        "page": str(page),
    }
    category_id = normalize_category(category)
    if category_id:
        params["category"] = category_id
    if price_min is not None or price_max is not None:
        lo = int(price_min) if price_min is not None else ""
        hi = int(price_max) if price_max is not None else ""
        params["price"] = f"{lo}-{hi}"
    query = urllib.parse.urlencode(params)
    return f"{LEBONCOIN_BASE_URL}?{query}"


def reader_url(target_url: str) -> str:
    return JINA_READER + target_url


def detect_block(status: Optional[int], html: str) -> bool:
    if status in (403, 429, 503):
        return True
    lowered = html.lower()
    return any(marker in lowered for marker in BLOCK_MARKERS)


def probe_reader_block(session: requests.Session, target_url: str) -> Optional[str]:
    """Ask the reader for markdown and return its block diagnostic, if any.

    The HTML mode can return a client-rendered shell without an explicit
    challenge, while the markdown mode surfaces the reader's own warning
    ("This page maybe requiring CAPTCHA"). This is a classification probe,
    not a bypass attempt.
    """
    try:
        response = session.get(reader_url(target_url), headers=READER_MARKDOWN_HEADERS, timeout=REQUEST_TIMEOUT)
    except Exception:
        return None
    text = response.content.decode("utf-8", "replace")
    if detect_block(response.status_code, text):
        return "Leboncoin returned a DataDome/CAPTCHA challenge through the reader; use CSV import"
    return None


def parse_ads(html: str) -> tuple[list[dict[str, Any]], Optional[int]]:
    match = NEXT_DATA_RE.search(html)
    if not match:
        return [], None
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise ScrapeError(f"__NEXT_DATA__ is not valid JSON: {exc}") from exc
    search_data = (
        data.get("props", {}).get("pageProps", {}).get("searchData", {}) or {}
    )
    ads = search_data.get("ads") or []
    return list(ads), search_data.get("total")


def _fetch_reader(
    session: requests.Session,
    text: str,
    page: int = 1,
    category: str = "",
    price_min=None,
    price_max=None,
    retries: int = 3,
    backoff: float = 5.0,
) -> ScrapePage:
    target_url = build_url(text, page, category, price_min, price_max)
    url = reader_url(target_url)
    last_error: Optional[str] = None

    for attempt in range(1, retries + 1):
        try:
            response = session.get(url, headers=JINA_HEADERS, timeout=REQUEST_TIMEOUT)
        except Exception as exc:  # network/proxy failure
            last_error = f"connection error: {exc}"
            if attempt < retries:
                time.sleep(backoff * attempt)
                continue
            return ScrapePage(error=last_error)

        html = response.content.decode("utf-8", "replace")
        if response.status_code in (403, 429, 503):
            return ScrapePage(
                blocked=True,
                error=f"HTTP {response.status_code}: page looks blocked (DataDome/reader)",
            )

        if response.status_code != 200:
            last_error = f"HTTP {response.status_code}"
            if attempt < retries:
                time.sleep(backoff * attempt)
                continue
            return ScrapePage(error=last_error)

        try:
            ads, total = parse_ads(html)
        except ScrapeError as exc:
            last_error = str(exc)
            if attempt < retries:
                time.sleep(backoff * attempt)
                continue
            return ScrapePage(error=last_error)

        if ads or NEXT_DATA_RE.search(html):
            # An empty result set with a real Next.js payload is a valid page.
            return ScrapePage(ads=ads, total=total)

        # A healthy page can embed the DataDome SDK text, so the marker check
        # only applies after the payload turned out to be ad-free.
        if detect_block(200, html):
            return ScrapePage(
                blocked=True,
                error="HTTP 200: page looks blocked (DataDome/reader)",
            )

        if not ads and attempt < retries:
            # reader sometimes returns a shell before hydration; retry once
            last_error = "no ads in payload"
            time.sleep(backoff * attempt)
            continue

        if not ads:
            reason = probe_reader_block(session, target_url)
            if reason:
                return ScrapePage(blocked=True, error=reason)
            # No NEXT_DATA/ads after a successful HTML fetch: the reader
            # served a client-rendered shell without listing data.
            return ScrapePage(
                blocked=True,
                error="reader returned no ad payload (DataDome/CAPTCHA or client-rendered shell); use CSV import",
            )

        return ScrapePage(ads=ads, total=total)

    return ScrapePage(error=last_error or "unknown error")


def _fetch_direct(
    session: requests.Session,
    text: str,
    page: int = 1,
    category: str = "",
    price_min=None,
    price_max=None,
    **_: Any,
) -> ScrapePage:
    """Fetch Leboncoin directly with a browser-like TLS fingerprint (works from some home IPs)."""
    url = build_url(text, page, category, price_min, price_max)
    try:
        response = session.get(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "fr-FR,fr;q=0.9"}, timeout=REQUEST_TIMEOUT)
    except Exception as exc:
        return ScrapePage(error=f"connection error: {exc}")
    html = response.content.decode("utf-8", "replace")
    if response.status_code in (403, 429, 503):
        return ScrapePage(blocked=True, error=f"HTTP {response.status_code}: direct fetch blocked (DataDome)")
    if response.status_code != 200:
        return ScrapePage(error=f"HTTP {response.status_code}")
    try:
        ads, total = parse_ads(html)
    except ScrapeError as exc:
        return ScrapePage(error=str(exc))
    if ads or NEXT_DATA_RE.search(html):
        return ScrapePage(ads=ads, total=total)
    if detect_block(200, html):
        return ScrapePage(blocked=True, error="HTTP 200: direct fetch shows a challenge page")
    return ScrapePage(error="no ad payload in direct response")


def fetch_page(session: requests.Session, text: str, page: int = 1, **kwargs: Any) -> ScrapePage:
    """Try each configured strategy (default: reader, then direct) until one returns ads."""
    last = ScrapePage(error="no scrape strategy configured")
    for name in SCRAPE_STRATEGIES:
        func = _fetch_direct if name == "direct" else _fetch_reader
        result = func(session, text, page=page, **kwargs)
        result.strategy = name
        if not (result.blocked or result.error):
            return result
        last = result
    return last


AD_GONE_MARKERS = (
    "n'est plus disponible",
    "n’est plus disponible",
    "cette annonce n'existe plus",
    "cette annonce n’existe plus",
    "annonce supprimée",
    "annonce expirée",
    "page introuvable",
)


def classify_ad_page(status: Optional[int], html: str) -> str:
    """'active' | 'gone' | 'unknown' for a fetched ad page."""
    if status in (404, 410):
        return "gone"
    lowered = html.lower()
    if any(marker in lowered for marker in AD_GONE_MARKERS):
        return "gone"
    match = NEXT_DATA_RE.search(html)
    if match:
        try:
            ad = (json.loads(match.group(1)).get("props", {}).get("pageProps", {}) or {}).get("ad") or {}
        except json.JSONDecodeError:
            ad = {}
        if ad:
            return "gone" if str(ad.get("status", "active")).lower() in ("deleted", "expired", "sold", "inactive") else "active"
    if status == 200 and not detect_block(status, html) and len(html) > 2000:
        return "active"
    return "unknown"


def check_ad_status(session: requests.Session, ad_url: str) -> str:
    """Is the ad still online? Never raises; blocked/failed checks return 'unknown'."""
    if not ad_url:
        return "unknown"
    urls = [reader_url(ad_url)] if "reader" in SCRAPE_STRATEGIES else []
    if "direct" in SCRAPE_STRATEGIES:
        urls.append(ad_url)
    for url in urls:
        try:
            response = session.get(url, headers=JINA_HEADERS if url.startswith(JINA_READER) else {"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        except Exception:
            continue
        state = classify_ad_page(response.status_code, response.content.decode("utf-8", "replace"))
        if state != "unknown":
            return state
    return "unknown"


def _first_price(raw: dict[str, Any]) -> tuple[Optional[int], Optional[float]]:
    cents = raw.get("price_cents")
    if isinstance(cents, (int, float)) and cents > 0:
        return int(cents), float(cents) / 100.0
    price = raw.get("price")
    if isinstance(price, list) and price:
        try:
            return None, float(price[0])
        except (TypeError, ValueError):
            return None, None
    if isinstance(price, (int, float)) and price > 0:
        return None, float(price)
    return None, None


def _attr_map(raw: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for attribute in raw.get("attributes") or []:
        key = attribute.get("key")
        if not key:
            continue
        value = attribute.get("value")
        values = attribute.get("values")
        if value in (None, ""):
            value = attribute.get("value_label")
        if value in (None, "") and isinstance(values, list) and values:
            value = values[0]
        result[key] = value
    return result


def _images(raw: dict[str, Any]) -> list[str]:
    images = raw.get("images")
    if isinstance(images, dict):
        for key in ("urls_large", "urls", "urls_thumb", "small_url", "thumb_url"):
            value = images.get(key)
            if isinstance(value, str) and value:
                return [value]
            if isinstance(value, list):
                urls = [
                    item if isinstance(item, str) else (item.get("url") or item.get("src") or "")
                    for item in value
                    if isinstance(item, (str, dict))
                ]
                urls = [url for url in urls if url]
                if urls:
                    return urls
        return []

    urls: list[str] = []
    for image in images or []:
        if isinstance(image, str):
            urls.append(image)
        elif isinstance(image, dict):
            url = image.get("url") or image.get("src")
            if url:
                urls.append(url)
    return urls


def normalize_ad(raw: dict[str, Any]) -> dict[str, Any]:
    price_cents, price_eur = _first_price(raw)
    location = raw.get("location") or {}
    attributes = _attr_map(raw)
    owner = raw.get("owner") or {}
    category_id = raw.get("category_id")
    url = raw.get("url") or ""
    if url and url.startswith("/"):
        url = "https://www.leboncoin.fr" + url

    return {
        "list_id": str(raw.get("list_id")) if raw.get("list_id") is not None else None,
        "url": url,
        "subject": raw.get("subject") or "",
        "price_cents": price_cents,
        "price_eur": price_eur,
        "category_id": str(category_id) if category_id is not None else "",
        "city": location.get("city") or "",
        "zipcode": location.get("zipcode") or "",
        "department": location.get("department_name") or location.get("region_name") or "",
        "brand": attributes.get("brand") or "",
        "condition": attributes.get("condition") or attributes.get("item_condition") or "",
        "description": raw.get("body") or "",
        "images": _images(raw),
        "first_publication_date": raw.get("first_publication_date") or "",
        "index_date": raw.get("index_date") or "",
        "seller_id": str(owner.get("user_id") or owner.get("store_id") or "") if owner else "",
        "is_boosted": bool(raw.get("is_boosted")),
        "is_pro": (owner.get("type") == "pro") if owner else False,
        "raw": raw,
    }


def make_session() -> requests.Session:
    if PROXY_URL:
        return requests.Session(impersonate="chrome", proxies={"http": PROXY_URL, "https": PROXY_URL})
    return requests.Session(impersonate="chrome")
