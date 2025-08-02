"""Test package for Builder MCP."""

from unittest.mock import Mock, patch

from connector_builder_mcp._connector_builder import (
    ManifestValidationResult,
    StreamTestResult,
    execute_stream_test_read,
    get_resolved_manifest,
    validate_manifest,
)


class TestManifestValidation:
    """Test manifest validation functionality."""

    def test_validate_manifest_missing_required_fields(self):
        """Test validation fails for manifest missing required fields."""
        manifest = {"version": "0.1.0"}

        result = validate_manifest(manifest)

        assert isinstance(result, ManifestValidationResult)
        assert not result.is_valid
        assert len(result.errors) > 0
        assert "missing required fields" in result.errors[0]

    def test_validate_manifest_basic_structure(self):
        """Test validation with basic valid manifest structure."""
        manifest = {
            "version": "0.1.0",
            "type": "DeclarativeSource",
            "check": {"type": "CheckStream"},
            "streams": [],
        }

        with patch("connector_builder_mcp._connector_builder.create_source"):
            with patch("connector_builder_mcp._connector_builder.resolve_manifest") as mock_resolve:
                mock_result = Mock()
                mock_result.type.value = "RECORD"
                mock_result.record.data = {"manifest": {"resolved": True}}
                mock_resolve.return_value = mock_result

                result = validate_manifest(manifest)

                assert isinstance(result, ManifestValidationResult)
                assert result.is_valid
                assert len(result.errors) == 0


class TestStreamTesting:
    """Test stream testing functionality."""

    def test_stream_read_success_no_records(self):
        """Test successful stream reading with include_records=False."""
        manifest = {
            "version": "0.1.0",
            "type": "DeclarativeSource",
            "check": {"type": "CheckStream"},
            "streams": [{"name": "test_stream"}],
        }
        config = {"api_key": "test_key"}

        with patch("connector_builder_mcp._connector_builder.create_source"):
            with patch("connector_builder_mcp._connector_builder.read_stream") as mock_read:
                mock_result = Mock()
                mock_result.type.value = "RECORD"
                mock_read.return_value = mock_result

                result = execute_stream_test_read(
                    manifest, config, "test_stream", 5, include_records=False
                )

                assert isinstance(result, StreamTestResult)
                assert result.success
                assert "Successfully read from stream" in result.message
                assert result.records is None

    def test_stream_read_failure(self):
        """Test stream reading failure handling."""
        manifest = {
            "version": "0.1.0",
            "type": "DeclarativeSource",
            "check": {"type": "CheckStream"},
            "streams": [{"name": "test_stream"}],
        }
        config = {"api_key": "test_key"}

        with patch("connector_builder_mcp._connector_builder.create_source"):
            with patch("connector_builder_mcp._connector_builder.read_stream") as mock_read:
                mock_result = Mock()
                mock_result.type.value = "TRACE"
                mock_result.trace.error.message = "Connection failed"
                mock_read.return_value = mock_result

                result = execute_stream_test_read(manifest, config, "test_stream", 5)

                assert isinstance(result, StreamTestResult)
                assert not result.success
                assert len(result.errors) > 0

    def test_stream_read_success_with_records(self):
        """Test successful stream reading with include_records=True."""
        manifest = {
            "version": "0.1.0",
            "type": "DeclarativeSource",
            "check": {"type": "CheckStream"},
            "streams": [{"name": "test_stream"}],
        }
        config = {"api_key": "test_key"}

        with patch("connector_builder_mcp._connector_builder.create_source"):
            with patch("connector_builder_mcp._connector_builder.read_stream") as mock_read:
                mock_result = Mock()
                mock_result.type.value = "RECORD"
                mock_result.record = Mock()
                mock_result.record.data = {
                    "records": [{"id": 1, "name": "test1"}, {"id": 2, "name": "test2"}]
                }
                mock_read.return_value = mock_result

                result = execute_stream_test_read(
                    manifest, config, "test_stream", 5, include_records=True
                )

                assert isinstance(result, StreamTestResult)
                assert result.success
                assert "Successfully read from stream" in result.message
                assert result.records is not None
                assert len(result.records) == 2
                assert result.records[0]["id"] == 1
                assert result.records[1]["name"] == "test2"

    def test_stream_read_with_raw_requests_success(self):
        """Test successful stream reading with include_raw_requests=True."""
        manifest = {
            "version": "0.1.0",
            "type": "DeclarativeSource",
            "check": {"type": "CheckStream"},
            "streams": [{"name": "test_stream"}],
        }
        config = {"api_key": "test_key"}

        with patch("connector_builder_mcp._connector_builder.create_source"):
            with patch("connector_builder_mcp._connector_builder.read_stream") as mock_read:
                mock_result = Mock()
                mock_result.type.value = "RECORD"
                mock_result.record = Mock()
                mock_result.record.data = {
                    "slices": [
                        {
                            "pages": [
                                {
                                    "request": {
                                        "url": "https://api.example.com/test",
                                        "headers": {"Authorization": "Bearer token"},
                                        "http_method": "GET",
                                        "body": None,
                                    }
                                }
                            ]
                        }
                    ]
                }
                mock_read.return_value = mock_result

                result = execute_stream_test_read(
                    manifest, config, "test_stream", 5, include_raw_requests=True
                )

                assert isinstance(result, StreamTestResult)
                assert result.success
                assert result.raw_requests is not None
                assert len(result.raw_requests) == 1
                assert result.raw_requests[0]["url"] == "https://api.example.com/test"
                assert result.raw_requests[0]["http_method"] == "GET"

    def test_stream_read_with_raw_responses_success(self):
        """Test successful stream reading with include_raw_responses=True."""
        manifest = {
            "version": "0.1.0",
            "type": "DeclarativeSource",
            "check": {"type": "CheckStream"},
            "streams": [{"name": "test_stream"}],
        }
        config = {"api_key": "test_key"}

        with patch("connector_builder_mcp._connector_builder.create_source"):
            with patch("connector_builder_mcp._connector_builder.read_stream") as mock_read:
                mock_result = Mock()
                mock_result.type.value = "RECORD"
                mock_result.record = Mock()
                mock_result.record.data = {
                    "slices": [
                        {
                            "pages": [
                                {
                                    "response": {
                                        "status": 200,
                                        "headers": {"content-type": "application/json"},
                                        "body": '{"data": [{"id": 1}]}',
                                    }
                                }
                            ]
                        }
                    ]
                }
                mock_read.return_value = mock_result

                result = execute_stream_test_read(
                    manifest, config, "test_stream", 5, include_raw_responses=True
                )

                assert isinstance(result, StreamTestResult)
                assert result.success
                assert result.raw_responses is not None
                assert len(result.raw_responses) == 1
                assert result.raw_responses[0]["status"] == 200
                assert result.raw_responses[0]["body"] == '{"data": [{"id": 1}]}'

    def test_stream_read_failure_with_debug_data(self):
        """Test stream reading failure with debug data extraction (None defaults to True on failure)."""
        manifest = {
            "version": "0.1.0",
            "type": "DeclarativeSource",
            "check": {"type": "CheckStream"},
            "streams": [{"name": "test_stream"}],
        }
        config = {"api_key": "test_key"}

        with patch("connector_builder_mcp._connector_builder.create_source"):
            with patch("connector_builder_mcp._connector_builder.read_stream") as mock_read:
                mock_result = Mock()
                mock_result.type.value = "ERROR"
                mock_result.trace = Mock()
                mock_result.trace.error.message = "Connection failed"
                mock_result.record = Mock()
                mock_result.record.data = {
                    "slices": [
                        {
                            "pages": [
                                {
                                    "request": {
                                        "url": "https://api.example.com/test",
                                        "http_method": "GET",
                                    },
                                    "response": {"status": 500, "body": "Internal Server Error"},
                                }
                            ]
                        }
                    ]
                }
                mock_read.return_value = mock_result

                result = execute_stream_test_read(manifest, config, "test_stream", 5)

                assert isinstance(result, StreamTestResult)
                assert not result.success
                assert len(result.errors) > 0
                assert result.raw_requests is not None
                assert result.raw_responses is not None
                assert len(result.raw_requests) == 1
                assert len(result.raw_responses) == 1
                assert result.raw_requests[0]["url"] == "https://api.example.com/test"
                assert result.raw_responses[0]["status"] == 500

    def test_stream_read_with_records_fallback(self):
        """Test stream reading with include_records=True when records field is not present."""
        manifest = {
            "version": "0.1.0",
            "type": "DeclarativeSource",
            "check": {"type": "CheckStream"},
            "streams": [{"name": "test_stream"}],
        }
        config = {"api_key": "test_key"}

        with patch("connector_builder_mcp._connector_builder.create_source"):
            with patch("connector_builder_mcp._connector_builder.read_stream") as mock_read:
                mock_result = Mock()
                mock_result.type.value = "RECORD"
                mock_result.record = Mock()
                mock_result.record.data = {"some_field": "some_value"}
                mock_read.return_value = mock_result

                result = execute_stream_test_read(
                    manifest, config, "test_stream", 5, include_records=True
                )

                assert isinstance(result, StreamTestResult)
                assert result.success
                assert "Successfully read from stream" in result.message
                assert result.records is not None
                assert len(result.records) == 1
                assert result.records[0]["some_field"] == "some_value"


class TestManifestResolution:
    """Test manifest resolution functionality."""

    def test_resolve_manifest_success(self):
        """Test successful manifest resolution."""
        manifest = {
            "version": "0.1.0",
            "type": "DeclarativeSource",
            "check": {"type": "CheckStream"},
            "streams": [],
        }

        with patch("connector_builder_mcp._connector_builder.create_source"):
            with patch("connector_builder_mcp._connector_builder.resolve_manifest") as mock_resolve:
                mock_result = Mock()
                mock_result.type.value = "RECORD"
                mock_result.record.data = {"manifest": {"resolved": True}}
                mock_resolve.return_value = mock_result

                result = get_resolved_manifest(manifest)

                assert isinstance(result, dict)
                assert result.get("resolved") is True

    def test_resolve_manifest_failure(self):
        """Test manifest resolution failure handling."""
        manifest = {
            "version": "0.1.0",
            "type": "DeclarativeSource",
            "check": {"type": "CheckStream"},
            "streams": [],
        }

        with patch("connector_builder_mcp._connector_builder.create_source"):
            with patch("connector_builder_mcp._connector_builder.resolve_manifest") as mock_resolve:
                mock_result = Mock()
                mock_result.type.value = "TRACE"
                mock_resolve.return_value = mock_result

                result = get_resolved_manifest(manifest)

                assert result == "Failed to resolve manifest"
