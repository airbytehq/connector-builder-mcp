
"""Test package for Builder MCP."""
from unittest.mock import Mock, patch

from builder_mcp._connector_builder import (
    ManifestValidationResult,
    StreamTestResult,
    validate_manifest,
    execute_stream_read,
    get_resolved_manifest,
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
            "streams": []
        }
        
        with patch('builder_mcp._connector_builder.create_source') as mock_create:
            with patch('builder_mcp._connector_builder.resolve_manifest') as mock_resolve:
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

    def test_stream_read_success(self):
        """Test successful stream reading."""
        manifest = {
            "version": "0.1.0",
            "type": "DeclarativeSource",
            "check": {"type": "CheckStream"},
            "streams": [{"name": "test_stream"}]
        }
        config = {"api_key": "test_key"}
        
        with patch('builder_mcp._connector_builder.create_source') as mock_create:
            with patch('builder_mcp._connector_builder.read_stream') as mock_read:
                mock_result = Mock()
                mock_result.type.value = "RECORD"
                mock_read.return_value = mock_result
                
                result = execute_stream_read(manifest, config, "test_stream", 5)
                
                assert isinstance(result, StreamTestResult)
                assert result.success
                assert "Successfully read from stream" in result.message

    def test_stream_read_failure(self):
        """Test stream reading failure handling."""
        manifest = {
            "version": "0.1.0",
            "type": "DeclarativeSource", 
            "check": {"type": "CheckStream"},
            "streams": [{"name": "test_stream"}]
        }
        config = {"api_key": "test_key"}
        
        with patch('builder_mcp._connector_builder.create_source') as mock_create:
            with patch('builder_mcp._connector_builder.read_stream') as mock_read:
                mock_result = Mock()
                mock_result.type.value = "TRACE"
                mock_result.trace.error.message = "Connection failed"
                mock_read.return_value = mock_result
                
                result = execute_stream_read(manifest, config, "test_stream", 5)
                
                assert isinstance(result, StreamTestResult)
                assert not result.success
                assert len(result.errors) > 0


class TestManifestResolution:
    """Test manifest resolution functionality."""

    def test_resolve_manifest_success(self):
        """Test successful manifest resolution."""
        manifest = {
            "version": "0.1.0",
            "type": "DeclarativeSource",
            "check": {"type": "CheckStream"},
            "streams": []
        }
        
        with patch('builder_mcp._connector_builder.create_source') as mock_create:
            with patch('builder_mcp._connector_builder.resolve_manifest') as mock_resolve:
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
            "streams": []
        }
        
        with patch('builder_mcp._connector_builder.create_source') as mock_create:
            with patch('builder_mcp._connector_builder.resolve_manifest') as mock_resolve:
                mock_result = Mock()
                mock_result.type.value = "TRACE"
                mock_resolve.return_value = mock_result
                
                result = get_resolved_manifest(manifest)
                
                assert result == "Failed to resolve manifest"
