"""Tests for the connector manifest scaffold tool."""

import yaml

from connector_builder_mcp._manifest_scaffold import (
    AuthenticationType,
    PaginationType,
    create_connector_manifest_scaffold,
)
from connector_builder_mcp._validation_testing import validate_manifest


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

        assert result.success
        assert result.manifest_yaml is not None
        assert "source-test-api" in result.manifest_yaml
        assert result.validation_result.is_valid

    def test_invalid_connector_name(self):
        """Test validation of invalid connector names."""
        result = create_connector_manifest_scaffold(
            connector_name="invalid-name",
            api_base_url="https://api.example.com",
            initial_stream_name="users",
            initial_stream_path="/users",
            authentication_type="NoAuth",
        )

        assert not result.success
        assert "Input validation error" in result.errors[0]

    def test_api_key_authentication(self):
        """Test manifest generation with API key authentication."""
        result = create_connector_manifest_scaffold(
            connector_name="source-test-api",
            api_base_url="https://api.example.com",
            initial_stream_name="users",
            initial_stream_path="/users",
            authentication_type="ApiKeyAuthenticator",
        )

        assert result.success
        assert "ApiKeyAuthenticator" in result.manifest_yaml
        assert "api_key" in result.manifest_yaml

    def test_pagination_configuration(self):
        """Test manifest generation with pagination."""
        result = create_connector_manifest_scaffold(
            connector_name="source-test-api",
            api_base_url="https://api.example.com",
            initial_stream_name="users",
            initial_stream_path="/users",
            authentication_type="NoAuth",
            pagination_type="page_increment",
        )

        assert result.success
        assert "DefaultPaginator" in result.manifest_yaml
        assert "PageIncrement" in result.manifest_yaml

    def test_todo_placeholders(self):
        """Test that TODO placeholders are included in the manifest."""
        result = create_connector_manifest_scaffold(
            connector_name="source-test-api",
            api_base_url="https://api.example.com",
            initial_stream_name="users",
            initial_stream_path="/users",
            authentication_type="NoAuth",
            primary_key="TODO",
        )

        assert result.success
        assert "TODO" in result.manifest_yaml

        manifest_lines = result.manifest_yaml.split("\n")
        yaml_content = [line for line in manifest_lines if not line.strip().startswith("#")]

        manifest = yaml.safe_load("\n".join(yaml_content))
        assert manifest["streams"][0]["primary_key"] == ["TODO"]

    def test_all_generated_manifests_pass_validation(self):
        """Test that all generated manifests pass validation regardless of inputs."""
        for auth_type in [at.value for at in AuthenticationType]:
            for pagination_type in [pt.value for pt in PaginationType]:
                result = create_connector_manifest_scaffold(
                    connector_name=f"source-test-{auth_type.lower().replace('authenticator', '').replace('auth', '').replace('_', '-')}-{pagination_type.replace('_', '-')}",
                    api_base_url="https://api.example.com",
                    initial_stream_name="users",
                    initial_stream_path="/users",
                    authentication_type=auth_type,
                    pagination_type=pagination_type,
                    primary_key="TODO",
                    record_selector_path=[],
                )

                assert result.success, (
                    f"Failed with auth_type={auth_type}, pagination_type={pagination_type}: {result.errors}"
                )
                assert result.validation_result.is_valid, (
                    f"Validation failed with auth_type={auth_type}, pagination_type={pagination_type}: {result.validation_result.errors}"
                )

                validation_result = validate_manifest(result.manifest_yaml)
                assert validation_result.is_valid, (
                    f"Direct validation failed with auth_type={auth_type}, pagination_type={pagination_type}: {validation_result.errors}"
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

        assert result.success
        assert "InlineSchemaLoader" in result.manifest_yaml
        assert "TODO" in result.manifest_yaml

    def test_incremental_sync_todo_comments(self):
        """Test that incremental sync TODO comments are included."""
        result = create_connector_manifest_scaffold(
            connector_name="source-test-api",
            api_base_url="https://api.example.com",
            initial_stream_name="users",
            initial_stream_path="/users",
            authentication_type="NoAuth",
        )

        assert result.success
        assert "DatetimeBasedCursor" in result.manifest_yaml
        assert "cursor_field" in result.manifest_yaml
        assert "# TODO: Uncomment and configure incremental sync" in result.manifest_yaml
