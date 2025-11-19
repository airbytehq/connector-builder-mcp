# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""External documentation URL suggestion with web search and metadata enrichment."""

import logging
import re
import time
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS


logger = logging.getLogger(__name__)

DOCUMENTATION_TYPES = Literal[
    "api_deprecations",
    "api_reference",
    "api_release_history",
    "authentication_guide",
    "data_model_reference",
    "developer_community",
    "migration_guide",
    "other",
    "permissions_scopes",
    "rate_limits",
    "sql_reference",
    "status_page",
]

CATEGORY_SEARCH_PATTERNS = {
    "api_release_history": ["changelog", "release notes", "what's new", "API changelog"],
    "api_reference": ["API reference", "API docs", "REST API", "API documentation"],
    "authentication_guide": ["OAuth", "authentication", "API key", "credentials"],
    "permissions_scopes": ["permissions", "scopes", "roles", "access control", "grants"],
    "rate_limits": ["rate limits", "quotas", "throttling", "API limits"],
    "status_page": ["status"],
    "data_model_reference": ["object reference", "data model", "schema", "objects"],
    "sql_reference": ["SQL reference", "language reference"],
    "migration_guide": ["migration", "upgrade", "breaking changes", "deprecations"],
    "api_deprecations": ["deprecations", "breaking changes", "sunset"],
}

URL_PATH_PATTERNS = {
    "api_release_history": [r"/changelog", r"/release-notes", r"/whats-new", r"/api/versions"],
    "api_reference": [r"/api/reference", r"/api/docs", r"/developers/api", r"/api-reference"],
    "authentication_guide": [
        r"/oauth",
        r"/authentication",
        r"/auth",
        r"/api-keys",
        r"/credentials",
    ],
    "permissions_scopes": [r"/permissions", r"/scopes", r"/roles", r"/access-control", r"/grants"],
    "rate_limits": [r"/rate-limits", r"/quotas", r"/limits", r"/throttling"],
    "status_page": [r"/status", r"/system-status"],
    "data_model_reference": [r"/object-reference", r"/data-model", r"/schema", r"/objects"],
    "sql_reference": [r"/sql-reference", r"/sql/reference", r"/language-reference"],
    "migration_guide": [r"/migration", r"/upgrade", r"/version-migration"],
    "api_deprecations": [r"/deprecations", r"/breaking-changes", r"/sunset"],
}

PREFERRED_SUBDOMAINS = ["docs", "developers", "api", "status", "developer"]

DENYLIST_DOMAINS = [
    "stackoverflow.com",
    "medium.com",
    "postman.com",
    "rapidapi.com",
    "github.com",  # Unless it's the vendor's org
]


@dataclass
class URLCandidate:
    """A candidate URL with metadata."""

    url: str
    title: str
    category: str
    score: float
    title_source: str
    requires_login: bool = False


def _derive_vendor_domain(
    api_name: str, api_base_url: str | None, vendor_domain: str | None
) -> str:
    """Derive the vendor domain from available information."""
    if vendor_domain:
        return vendor_domain

    if api_base_url:
        parsed = urlparse(api_base_url)
        domain = parsed.netloc
        parts = domain.split(".")
        if len(parts) > 2 and parts[0] in ["api", "www"]:
            return ".".join(parts[1:])
        return domain

    try:
        results = DDGS().text(f"{api_name} developer docs", max_results=3)
        if results:
            for result in results:
                url = result.get("href", "")
                parsed = urlparse(url)
                domain = parsed.netloc
                if any(sub in domain for sub in PREFERRED_SUBDOMAINS):
                    parts = domain.split(".")
                    if len(parts) > 2 and parts[0] in PREFERRED_SUBDOMAINS:
                        return ".".join(parts[1:])
                    return domain
    except Exception as e:
        logger.warning(f"Failed to derive vendor domain via search: {e}")

    return api_name.lower().replace(" ", "").replace("-", "")


def _is_official_domain(url: str, vendor_domain: str) -> bool:
    """Check if URL is from an official vendor domain."""
    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    if vendor_domain.lower() in domain:
        return True

    for denied in DENYLIST_DOMAINS:
        if denied in domain:
            return False

    return False


def _score_url(url: str, category: str, vendor_domain: str, search_title: str = "") -> float:
    """Score a URL based on various heuristics."""
    score = 0.0
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    path = parsed.path.lower()

    if vendor_domain.lower() in domain:
        score += 50.0
        for subdomain in PREFERRED_SUBDOMAINS:
            if domain.startswith(f"{subdomain}."):
                score += 20.0
                break

    if category in URL_PATH_PATTERNS:
        for pattern in URL_PATH_PATTERNS[category]:
            if re.search(pattern, path, re.IGNORECASE):
                score += 30.0
                break

    if re.search(r"/(en-us|en_us|en-gb|en_gb)/", path, re.IGNORECASE):
        score -= 10.0

    if re.search(r"/v\d+(\.\d+)?/", path):
        score -= 5.0

    if "#" in url and len(url.split("#")[1]) > 20:
        score -= 5.0

    if search_title and category in CATEGORY_SEARCH_PATTERNS:
        for keyword in CATEGORY_SEARCH_PATTERNS[category]:
            if keyword.lower() in search_title.lower():
                score += 10.0
                break

    return max(0.0, score)


def _canonicalize_url(url: str) -> str:
    """Canonicalize URL by removing locale, trailing slashes, etc."""
    url = re.sub(r"/(en-us|en_us|en-gb|en_gb)/", "/", url, flags=re.IGNORECASE)

    if url.endswith("/") and url.count("/") > 3:
        url = url.rstrip("/")

    return url


def _validate_url(url: str) -> tuple[bool, bool, str]:
    """Validate URL and check if it requires login.

    Returns:
        (is_valid, requires_login, final_url)
    """
    try:
        response = requests.head(
            url, allow_redirects=True, timeout=10, headers={"User-Agent": "Mozilla/5.0"}
        )

        final_url = response.url if hasattr(response, "url") else url

        if response.status_code in [200, 301, 302, 303]:
            return True, False, final_url
        elif response.status_code in [401, 403]:
            return True, True, final_url
        else:
            return False, False, url

    except requests.exceptions.RequestException:
        try:
            response = requests.get(
                url,
                allow_redirects=True,
                timeout=10,
                stream=True,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            final_url = response.url if hasattr(response, "url") else url

            if response.status_code in [200, 301, 302, 303]:
                return True, False, final_url
            elif response.status_code in [401, 403]:
                return True, True, final_url
            else:
                return False, False, url

        except Exception as e:
            logger.warning(f"Failed to validate URL {url}: {e}")
            return False, False, url


def _enrich_title(url: str, search_title: str, category: str, vendor_name: str) -> tuple[str, str]:
    """Enrich title by fetching page metadata.

    Returns:
        (enriched_title, title_source)
    """
    try:
        response = requests.get(
            url,
            timeout=10,
            stream=True,
            headers={"User-Agent": "Mozilla/5.0"},
        )

        content = response.raw.read(50000)
        soup = BeautifulSoup(content, "lxml")

        og_title_tag = soup.find("meta", property="og:title")
        if og_title_tag and og_title_tag.get("content"):
            content = og_title_tag["content"]
            if isinstance(content, str):
                title = content.strip()
                if title:
                    return _clean_title(title), "og_title"

        twitter_title_tag = soup.find("meta", attrs={"name": "twitter:title"})
        if twitter_title_tag and twitter_title_tag.get("content"):
            content = twitter_title_tag["content"]
            if isinstance(content, str):
                title = content.strip()
                if title:
                    return _clean_title(title), "twitter_title"

        h1_tag = soup.find("h1")
        if h1_tag:
            title = h1_tag.get_text().strip()
            if title:
                return _clean_title(title), "h1"

        title_tag = soup.find("title")
        if title_tag:
            title = title_tag.get_text().strip()
            if title:
                return _clean_title(title), "html_title"

    except Exception as e:
        logger.debug(f"Failed to enrich title for {url}: {e}")

    if search_title:
        return _clean_title(search_title), "search_result"

    return _generate_canonical_title(vendor_name, category), "canonical"


def _clean_title(title: str) -> str:
    """Clean title by removing common suffixes and prefixes."""
    suffixes = [
        r"\s*\|\s*.*?Docs?$",
        r"\s*\|\s*.*?Documentation$",
        r"\s*-\s*Developer$",
        r"\s*\|\s*.*?Developer.*$",
    ]
    for suffix in suffixes:
        title = re.sub(suffix, "", title, flags=re.IGNORECASE)

    title = re.sub(r"\s+", " ", title).strip()

    return title


def _generate_canonical_title(vendor_name: str, category: str) -> str:
    """Generate a canonical title for a category."""
    category_names = {
        "api_release_history": "API changelog",
        "api_reference": "API reference",
        "authentication_guide": "authentication guide",
        "permissions_scopes": "permissions and scopes",
        "rate_limits": "rate limits",
        "status_page": "Status",
        "data_model_reference": "data model reference",
        "sql_reference": "SQL reference",
        "migration_guide": "migration guide",
        "api_deprecations": "API deprecations",
        "developer_community": "developer community",
    }

    category_name = category_names.get(category, category.replace("_", " "))
    return f"{vendor_name} {category_name}"


def _search_for_category(
    category: str, vendor_domain: str, vendor_name: str, max_results: int = 3
) -> list[URLCandidate]:
    """Search for URLs in a specific category."""
    candidates = []

    if category == "status_page":
        status_url = f"https://status.{vendor_domain}"
        is_valid, requires_login, final_url = _validate_url(status_url)
        if is_valid:
            title, title_source = _enrich_title(final_url, "", category, vendor_name)
            candidates.append(
                URLCandidate(
                    url=final_url,
                    title=title,
                    category=category,
                    score=100.0,
                    title_source=title_source,
                    requires_login=requires_login,
                )
            )
            return candidates

    search_patterns = CATEGORY_SEARCH_PATTERNS.get(category, [])
    for pattern in search_patterns[:2]:  # Limit to first 2 patterns to reduce queries
        query = f'site:{vendor_domain} "{pattern}"'
        try:
            results = DDGS().text(query, max_results=max_results)
            time.sleep(0.5)  # Rate limiting

            for result in results:
                url = result.get("href", "")
                search_title = result.get("title", "")

                if not url or not _is_official_domain(url, vendor_domain):
                    continue

                url = _canonicalize_url(url)

                is_valid, requires_login, final_url = _validate_url(url)
                if not is_valid:
                    continue

                score = _score_url(final_url, category, vendor_domain, search_title)

                title, title_source = _enrich_title(final_url, search_title, category, vendor_name)

                candidates.append(
                    URLCandidate(
                        url=final_url,
                        title=title,
                        category=category,
                        score=score,
                        title_source=title_source,
                        requires_login=requires_login,
                    )
                )

            if candidates:
                break  # Found results, no need to try more patterns

        except Exception as e:
            logger.warning(f"Search failed for category {category} with pattern '{pattern}': {e}")
            continue

    return candidates


def suggest_external_documentation_urls(
    api_name: str,
    vendor_domain: str | None = None,
    api_base_url: str | None = None,
    allowed_types: list[str] | None = None,
    max_results_per_type: int = 1,
) -> list[dict]:
    """Suggest external documentation URLs for an API.

    Args:
        api_name: Name of the API (e.g., "Stripe", "Salesforce")
        vendor_domain: Optional vendor domain (e.g., "stripe.com")
        api_base_url: Optional API base URL (e.g., "https://api.stripe.com")
        allowed_types: Optional list of documentation types to search for
        max_results_per_type: Maximum number of results per type (default: 1)

    Returns:
        List of suggested URLs with metadata
    """
    vendor_domain = _derive_vendor_domain(api_name, api_base_url, vendor_domain)
    vendor_name = api_name

    logger.info(f"Suggesting external docs for {api_name} (domain: {vendor_domain})")

    categories_to_search = allowed_types or list(CATEGORY_SEARCH_PATTERNS.keys())

    all_candidates: list[URLCandidate] = []
    for category in categories_to_search:
        candidates = _search_for_category(category, vendor_domain, vendor_name)
        all_candidates.extend(candidates)

    all_candidates.sort(key=lambda c: c.score, reverse=True)

    results_by_category: dict[str, list[URLCandidate]] = {}
    for candidate in all_candidates:
        if candidate.category not in results_by_category:
            results_by_category[candidate.category] = []

        if len(results_by_category[candidate.category]) < max_results_per_type:
            is_duplicate = False
            for existing in results_by_category[candidate.category]:
                if _are_urls_similar(candidate.url, existing.url):
                    is_duplicate = True
                    break

            if not is_duplicate:
                results_by_category[candidate.category].append(candidate)

    results = []
    for _category, candidates in results_by_category.items():
        for candidate in candidates:
            results.append(
                {
                    "title": candidate.title,
                    "url": candidate.url,
                    "type": candidate.category,
                    "requiresLogin": candidate.requires_login,
                }
            )

    logger.info(f"Found {len(results)} external documentation URLs for {api_name}")
    return results


def _are_urls_similar(url1: str, url2: str) -> bool:
    """Check if two URLs are similar (same base path)."""
    parsed1 = urlparse(url1)
    parsed2 = urlparse(url2)

    if parsed1.netloc != parsed2.netloc:
        return False

    path1 = parsed1.path.rstrip("/")
    path2 = parsed2.path.rstrip("/")

    return path1 == path2 or path1.startswith(path2) or path2.startswith(path1)
