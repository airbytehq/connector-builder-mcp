# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Unit tests for external documentation URL suggestion."""

import pytest

from connector_builder_mcp._external_docs_suggester import (
    _are_urls_similar,
    _canonicalize_url,
    _clean_title,
    _derive_vendor_domain,
    _generate_canonical_title,
    _is_official_domain,
    _score_url,
)


@pytest.mark.parametrize(
    "api_name,api_base_url,vendor_domain,expected",
    [
        pytest.param(
            "Stripe",
            None,
            "stripe.com",
            "stripe.com",
            id="explicit_vendor_domain",
        ),
        pytest.param(
            "Stripe",
            "https://api.stripe.com/v1",
            None,
            "stripe.com",
            id="derive_from_api_url",
        ),
        pytest.param(
            "Stripe",
            "https://www.stripe.com",
            None,
            "stripe.com",
            id="strip_www_subdomain",
        ),
        pytest.param(
            "GitHub",
            "https://api.github.com",
            None,
            "github.com",
            id="strip_api_subdomain",
        ),
    ],
)
def test_derive_vendor_domain(api_name, api_base_url, vendor_domain, expected):
    result = _derive_vendor_domain(api_name, api_base_url, vendor_domain)
    assert result == expected


@pytest.mark.parametrize(
    "url,vendor_domain,expected",
    [
        pytest.param(
            "https://docs.stripe.com/api",
            "stripe.com",
            True,
            id="official_subdomain",
        ),
        pytest.param(
            "https://stripe.com/docs",
            "stripe.com",
            True,
            id="official_main_domain",
        ),
        pytest.param(
            "https://stackoverflow.com/questions/stripe",
            "stripe.com",
            False,
            id="denylisted_domain",
        ),
        pytest.param(
            "https://medium.com/stripe-blog",
            "stripe.com",
            False,
            id="denylisted_medium",
        ),
    ],
)
def test_is_official_domain(url, vendor_domain, expected):
    result = _is_official_domain(url, vendor_domain)
    assert result == expected


def test_score_url_official_domain():
    score = _score_url(
        "https://docs.stripe.com/api",
        "api_reference",
        "stripe.com",
        "Stripe API Reference",
    )
    assert score > 50.0


def test_score_url_preferred_subdomain():
    score = _score_url(
        "https://docs.stripe.com/api",
        "api_reference",
        "stripe.com",
        "",
    )
    assert score >= 70.0


def test_score_url_path_pattern_match():
    score = _score_url(
        "https://stripe.com/docs/changelog",
        "api_release_history",
        "stripe.com",
        "",
    )
    assert score >= 80.0


def test_score_url_penalize_locale():
    score_with_locale = _score_url(
        "https://docs.stripe.com/en-us/api",
        "api_reference",
        "stripe.com",
        "",
    )
    score_without_locale = _score_url(
        "https://docs.stripe.com/api",
        "api_reference",
        "stripe.com",
        "",
    )
    assert score_without_locale > score_with_locale


@pytest.mark.parametrize(
    "url,expected",
    [
        pytest.param(
            "https://docs.stripe.com/en-us/api",
            "https://docs.stripe.com/api",
            id="remove_locale",
        ),
        pytest.param(
            "https://docs.stripe.com/api/",
            "https://docs.stripe.com/api",
            id="remove_trailing_slash",
        ),
        pytest.param(
            "https://docs.stripe.com/en_us/api/",
            "https://docs.stripe.com/api",
            id="remove_locale_and_slash",
        ),
        pytest.param(
            "https://docs.stripe.com/",
            "https://docs.stripe.com/",
            id="keep_root_slash",
        ),
    ],
)
def test_canonicalize_url(url, expected):
    result = _canonicalize_url(url)
    assert result == expected


@pytest.mark.parametrize(
    "title,expected",
    [
        pytest.param(
            "API Reference | Stripe Documentation",
            "API Reference",
            id="remove_pipe_suffix",
        ),
        pytest.param(
            "Changelog - Developer",
            "Changelog",
            id="remove_dash_developer",
        ),
        pytest.param(
            "API  Reference   Guide",
            "API Reference Guide",
            id="collapse_whitespace",
        ),
        pytest.param(
            "  API Reference  ",
            "API Reference",
            id="trim_whitespace",
        ),
    ],
)
def test_clean_title(title, expected):
    result = _clean_title(title)
    assert result == expected


@pytest.mark.parametrize(
    "vendor_name,category,expected",
    [
        pytest.param(
            "Stripe",
            "api_release_history",
            "Stripe API Changelog",
            id="changelog",
        ),
        pytest.param(
            "Stripe",
            "api_reference",
            "Stripe API Reference",
            id="api_reference",
        ),
        pytest.param(
            "Stripe",
            "rate_limits",
            "Stripe Rate Limits",
            id="rate_limits",
        ),
        pytest.param(
            "Stripe",
            "status_page",
            "Stripe Status",
            id="status_page",
        ),
    ],
)
def test_generate_canonical_title(vendor_name, category, expected):
    result = _generate_canonical_title(vendor_name, category)
    assert result == expected


@pytest.mark.parametrize(
    "url1,url2,expected",
    [
        pytest.param(
            "https://docs.stripe.com/api",
            "https://docs.stripe.com/api",
            True,
            id="exact_match",
        ),
        pytest.param(
            "https://docs.stripe.com/api",
            "https://docs.stripe.com/api/",
            True,
            id="trailing_slash_difference",
        ),
        pytest.param(
            "https://docs.stripe.com/api",
            "https://docs.stripe.com/api/reference",
            True,
            id="one_is_prefix",
        ),
        pytest.param(
            "https://docs.stripe.com/api",
            "https://docs.stripe.com/changelog",
            False,
            id="different_paths",
        ),
        pytest.param(
            "https://docs.stripe.com/api",
            "https://developers.stripe.com/api",
            False,
            id="different_domains",
        ),
    ],
)
def test_are_urls_similar(url1, url2, expected):
    result = _are_urls_similar(url1, url2)
    assert result == expected
