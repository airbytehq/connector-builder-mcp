"""Test Privatebin integration."""
import os
from unittest.mock import patch

import pytest

from connector_builder_mcp._secrets import _load_secrets


@pytest.mark.xfail(reason="External privatebin URL has expired")
@patch.dict(os.environ, {"PRIVATEBIN_PASSWORD": "PASSWORD"})
def test_privatebin_integration() -> None:
    """Test loading secrets from real privatebin URL with expected values."""
    privatebin_url = (
        "https://privatebin.net/?187565d30322596b#H2VnHSogPPb1jyVzEmM8EaNY5KKzs3M9j8gLJy7pY1Mp"
    )

    secrets = _load_secrets(privatebin_url)

    assert secrets.get("answer") == "42", (
        f"Expected answer=42, got answer={secrets.get('answer')}"
    )
    assert secrets.get("foo") == "bar", f"Expected foo=bar, got foo={secrets.get('foo')}"

    expected_keys = {"answer", "foo"}
    actual_keys = set(secrets.keys())
    assert actual_keys == expected_keys, f"Expected keys {expected_keys}, got {actual_keys}"
