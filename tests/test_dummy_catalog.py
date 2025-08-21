# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Test dummy catalog creation."""
from airbyte_cdk.models import SyncMode
from connector_builder_mcp._validation_testing import _get_dummy_catalog


def test_get_dummy_catalog_basic() -> None:
    manifest_dict = {
        "streams": [
            {"name": "users"},
            {"name": "items"},
        ]
    }
    catalog = _get_dummy_catalog(
        manifest_dict,
    )
    stream_names = [s.stream.name for s in catalog.streams]
    assert stream_names == ["users", "items"]
    for s in catalog.streams:
        assert s.sync_mode == SyncMode.full_refresh

def test_get_dummy_catalog_empty() -> None:
    manifest_dict = {"streams": []}
    catalog = _get_dummy_catalog(manifest_dict)
    assert catalog.streams == []

def test_get_dummy_catalog_missing_name() -> None:
    manifest_dict = {
        "streams": [
            {},
            {"name": "foo"},
        ]
    }
    catalog = _get_dummy_catalog(manifest_dict)
    stream_names = [s.stream.name for s in catalog.streams]
    assert stream_names == ["unknown_stream", "foo"]
    for s in catalog.streams:
        assert s.sync_mode == SyncMode.full_refresh
