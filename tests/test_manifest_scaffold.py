"""Tests for the connector manifest scaffold tool."""

import yaml

from connector_builder_mcp.manifest_scaffold import (
    AuthenticationType,
    create_connector_manifest_scaffold,
)
from connector_builder_mcp.validation_testing import validate_manifest


class TestConnectorManifestScaffold:
    """Test the manifest scaffold creation tool."""

    def test_valid_basic_manifest(self):
        """Test creating a basic manifest with no auth and no pagination."""
        result = create_connector_manifest_scaffold(
            connector_name="source-test-api",
            api_base_url="https://api.example.com",
            initial_stream_name="users",
            initial_stream_path="/users",
            authentication_type="NoAuth",
        )

        assert isinstance(result, str)
        assert not result.startswith("ERROR:")
        assert "source-test-api" in result

    def test_invalid_connector_name(self):
        """Test validation of invalid connector names."""
        result = create_connector_manifest_scaffold(
            connector_name="invalid-name",
            api_base_url="https://api.example.com",
            initial_stream_name="users",
            initial_stream_path="/users",
            authentication_type="NoAuth",
        )

        assert isinstance(result, str)
        assert result.startswith("ERROR:")
        assert "Input validation error" in result

    def test_api_key_authentication(self):
        """Test manifest generation with API key authentication."""
        result = create_connector_manifest_scaffold(
            connector_name="source-test-api",
            api_base_url="https://api.example.com",
            initial_stream_name="users",
            initial_stream_path="/users",
            authentication_type="ApiKeyAuthenticator",
        )

        assert isinstance(result, str)
        assert not result.startswith("ERROR:")
        assert "ApiKeyAuthenticator" in result
        assert "api_key" in result

    def test_pagination_configuration(self):
        """Test manifest generation includes commented pagination block."""
        result = create_connector_manifest_scaffold(
            connector_name="source-test-api",
            api_base_url="https://api.example.com",
            initial_stream_name="users",
            initial_stream_path="/users",
            authentication_type="NoAuth",
        )

        assert isinstance(result, str)
        assert not result.startswith("ERROR:")
        assert "NoPagination" in result
        assert "# TODO: Uncomment and configure pagination when known" in result
        assert "# paginator:" in result
        assert "#   type: DefaultPaginator" in result

    def test_todo_placeholders(self):
        """Test that TODO placeholders are included in the manifest."""
        result = create_connector_manifest_scaffold(
            connector_name="source-test-api",
            api_base_url="https://api.example.com",
            initial_stream_name="users",
            initial_stream_path="/users",
            authentication_type="NoAuth",
        )

        assert isinstance(result, str)
        assert not result.startswith("ERROR:")
        assert "TODO" in result

        manifest_lines = result.split("\n")
        yaml_content = [line for line in manifest_lines if not line.strip().startswith("#")]

        manifest = yaml.safe_load("\n".join(yaml_content))
        assert manifest["streams"][0]["primary_key"] == ["TODO"]

    def test_all_generated_manifests_pass_validation(self):
        """Test that all generated manifests pass validation regardless of inputs."""
        for auth_type in [at.value for at in AuthenticationType]:
            result = create_connector_manifest_scaffold(
                connector_name=f"source-test-{auth_type.lower().replace('authenticator', '').replace('auth', '').replace('_', '-')}",
                api_base_url="https://api.example.com",
                initial_stream_name="users",
                initial_stream_path="/users",
                authentication_type=auth_type,
            )

            assert isinstance(result, str), f"Expected string, got {type(result)}"
            assert not result.startswith("ERROR:"), f"Failed with auth_type={auth_type}: {result}"

            validation_result = validate_manifest(result)
            assert validation_result.is_valid, (
                f"Direct validation failed with auth_type={auth_type}: {validation_result.errors}"
            )

    def test_dynamic_schema_loader_included(self):
        """Test that dynamic schema loader is included in generated manifests."""
        result = create_connector_manifest_scaffold(
            connector_name="source-test-api",
            api_base_url="https://api.example.com",
            initial_stream_name="users",
            initial_stream_path="/users",
            authentication_type="NoAuth",
        )

        assert isinstance(result, str)
        assert not result.startswith("ERROR:")
        assert "DynamicSchemaLoader" in result
        assert "TODO" in result

    def test_incremental_sync_todo_comments(self):
        """Test that incremental sync TODO comments are included."""
        result = create_connector_manifest_scaffold(
            connector_name="source-test-api",
            api_base_url="https://api.example.com",
            initial_stream_name="users",
            initial_stream_path="/users",
            authentication_type="NoAuth",
        )

        assert isinstance(result, str)
        assert not result.startswith("ERROR:")
        assert "DatetimeBasedCursor" in result
        assert "cursor_field" in result
        assert "# TODO: Uncomment and configure incremental sync" in result
