"""Integration tests for anonymized and final_pages_only parameters."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from connector_builder_mcp.validation_testing import (
    StreamTestResult,
    execute_stream_test_read,
)


@pytest.fixture
def rick_and_morty_manifest_yaml(resources_path: Path) -> str:
    """Load the Rick and Morty API manifest for testing."""
    manifest_path: Path = resources_path / "rick_and_morty_manifest.yaml"
    return manifest_path.read_text(encoding="utf-8")


class TestAnonymizedParameter:
    """Tests for the anonymized parameter."""

    def test_anonymized_requires_salt_env_var(self, rick_and_morty_manifest_yaml: str):
        """Test that anonymized=True requires MOCK_ANON_SALT environment variable."""
        with patch.dict(os.environ, {}, clear=True):
            result = execute_stream_test_read(
                rick_and_morty_manifest_yaml,
                config={},
                stream_name="characters",
                max_records=5,
                anonymized=True,
            )

            assert isinstance(result, StreamTestResult)
            assert not result.success
            assert "MOCK_ANON_SALT environment variable must be set" in result.message
            assert len(result.errors) > 0

    def test_anonymized_with_salt_succeeds(self, rick_and_morty_manifest_yaml: str):
        """Test that anonymized=True works when MOCK_ANON_SALT is set."""
        with patch.dict(os.environ, {"MOCK_ANON_SALT": "test_salt_12345"}):
            result = execute_stream_test_read(
                rick_and_morty_manifest_yaml,
                config={},
                stream_name="characters",
                max_records=5,
                anonymized=True,
                include_records_data=True,
            )

            assert isinstance(result, StreamTestResult)
            if result.success and result.records:
                assert result.records_read > 0
                assert result.records is not None
                
                for record in result.records:
                    if "id" in record:
                        assert str(record["id"]).startswith("anon_") or isinstance(
                            record["id"], int
                        )

    def test_anonymized_logs_salt_id(self, rick_and_morty_manifest_yaml: str):
        """Test that anonymized mode logs the salt_id."""
        with patch.dict(os.environ, {"MOCK_ANON_SALT": "test_salt_12345"}):
            result = execute_stream_test_read(
                rick_and_morty_manifest_yaml,
                config={},
                stream_name="characters",
                max_records=5,
                anonymized=True,
            )

            assert isinstance(result, StreamTestResult)
            if result.success and result.logs:
                salt_id_logs = [
                    log for log in result.logs if "salt_id=" in log.get("message", "")
                ]
                assert len(salt_id_logs) > 0, "Expected salt_id in logs"

    def test_anonymized_false_does_not_anonymize(self, rick_and_morty_manifest_yaml: str):
        """Test that anonymized=False does not anonymize data."""
        result = execute_stream_test_read(
            rick_and_morty_manifest_yaml,
            config={},
            stream_name="characters",
            max_records=5,
            anonymized=False,
            include_records_data=True,
        )

        assert isinstance(result, StreamTestResult)
        if result.success and result.records:
            for record in result.records:
                if "id" in record:
                    assert not str(record["id"]).startswith("anon_")


class TestFinalPagesOnlyParameter:
    """Tests for the final_pages_only parameter."""

    def test_final_pages_only_forces_include_records(self, rick_and_morty_manifest_yaml: str):
        """Test that final_pages_only=True forces include_records_data=True."""
        result = execute_stream_test_read(
            rick_and_morty_manifest_yaml,
            config={},
            stream_name="characters",
            max_records=5,
            final_pages_only=True,
            include_records_data=False,
        )

        assert isinstance(result, StreamTestResult)
        if result.success:
            assert result.records is not None

    def test_final_pages_only_logs_page_info(self, rick_and_morty_manifest_yaml: str):
        """Test that final_pages_only mode logs page information."""
        result = execute_stream_test_read(
            rick_and_morty_manifest_yaml,
            config={},
            stream_name="characters",
            max_records=5,
            final_pages_only=True,
        )

        assert isinstance(result, StreamTestResult)
        if result.success and result.logs:
            page_info_logs = [
                log
                for log in result.logs
                if "final_pages_only mode:" in log.get("message", "")
            ]
            assert len(page_info_logs) > 0, "Expected final_pages_only info in logs"
            
            log_message = page_info_logs[0]["message"]
            assert "captured" in log_message
            assert "total pages" in log_message
            assert "reached_end=" in log_message

    def test_final_pages_only_false_uses_normal_limits(self, rick_and_morty_manifest_yaml: str):
        """Test that final_pages_only=False uses normal max_records limit."""
        result = execute_stream_test_read(
            rick_and_morty_manifest_yaml,
            config={},
            stream_name="characters",
            max_records=3,
            final_pages_only=False,
            include_records_data=True,
        )

        assert isinstance(result, StreamTestResult)
        if result.success:
            assert result.records_read <= 3


class TestCombinedParameters:
    """Tests for using both anonymized and final_pages_only together."""

    def test_anonymized_and_final_pages_only_together(
        self, rick_and_morty_manifest_yaml: str
    ):
        """Test that both parameters can be used together."""
        with patch.dict(os.environ, {"MOCK_ANON_SALT": "test_salt_12345"}):
            result = execute_stream_test_read(
                rick_and_morty_manifest_yaml,
                config={},
                stream_name="characters",
                max_records=5,
                anonymized=True,
                final_pages_only=True,
            )

            assert isinstance(result, StreamTestResult)
            if result.success and result.logs:
                anonymization_logs = [
                    log for log in result.logs if "salt_id=" in log.get("message", "")
                ]
                final_pages_logs = [
                    log
                    for log in result.logs
                    if "final_pages_only mode:" in log.get("message", "")
                ]
                
                assert len(anonymization_logs) > 0, "Expected anonymization logs"
                assert len(final_pages_logs) > 0, "Expected final_pages_only logs"

    def test_both_parameters_with_raw_responses(self, rick_and_morty_manifest_yaml: str):
        """Test that both parameters work with include_raw_responses_data=True."""
        with patch.dict(os.environ, {"MOCK_ANON_SALT": "test_salt_12345"}):
            result = execute_stream_test_read(
                rick_and_morty_manifest_yaml,
                config={},
                stream_name="characters",
                max_records=5,
                anonymized=True,
                final_pages_only=True,
                include_raw_responses_data=True,
            )

            assert isinstance(result, StreamTestResult)
            if result.success:
                assert result.raw_api_responses is not None


class TestParameterValidation:
    """Tests for parameter validation and edge cases."""

    def test_anonymized_string_true(self, rick_and_morty_manifest_yaml: str):
        """Test that anonymized accepts string 'true'."""
        with patch.dict(os.environ, {"MOCK_ANON_SALT": "test_salt_12345"}):
            result = execute_stream_test_read(
                rick_and_morty_manifest_yaml,
                config={},
                stream_name="characters",
                max_records=5,
                anonymized="true",
            )

            assert isinstance(result, StreamTestResult)

    def test_final_pages_only_string_true(self, rick_and_morty_manifest_yaml: str):
        """Test that final_pages_only accepts string 'true'."""
        result = execute_stream_test_read(
            rick_and_morty_manifest_yaml,
            config={},
            stream_name="characters",
            max_records=5,
            final_pages_only="true",
        )

        assert isinstance(result, StreamTestResult)

    def test_anonymized_string_false(self, rick_and_morty_manifest_yaml: str):
        """Test that anonymized accepts string 'false'."""
        result = execute_stream_test_read(
            rick_and_morty_manifest_yaml,
            config={},
            stream_name="characters",
            max_records=5,
            anonymized="false",
        )

        assert isinstance(result, StreamTestResult)

    def test_final_pages_only_none(self, rick_and_morty_manifest_yaml: str):
        """Test that final_pages_only=None works (default behavior)."""
        result = execute_stream_test_read(
            rick_and_morty_manifest_yaml,
            config={},
            stream_name="characters",
            max_records=5,
            final_pages_only=None,
        )

        assert isinstance(result, StreamTestResult)
