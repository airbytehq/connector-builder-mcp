"""Tests for the connector manifest scaffold tool."""

import yaml

from connector_builder_mcp.manifest_scaffold import (
    AuthenticationType,
    create_connector_manifest_scaffold,
)
from connector_builder_mcp.session_manifest import (
    get_session_manifest_content,
    set_session_manifest_content,
)
from connector_builder_mcp.validation_testing import validate_manifest


def test_valid_basic_manifest(ctx) -> None:
    """Test creating a basic manifest with no auth and no pagination."""
    result = create_connector_manifest_scaffold(
        ctx,
        connector_name="source-test-api",
        api_base_url="https://api.example.com",
        initial_stream_name="users",
        initial_stream_path="/users",
        authentication_type="NoAuth",
    )

    assert isinstance(result, str)
    assert not result.startswith("ERROR:")
    assert "Manifest scaffold created successfully" in result

    manifest_content = get_session_manifest_content(ctx.session_id)
    assert manifest_content is not None
    assert "source-test-api" in manifest_content


def test_invalid_connector_name(ctx) -> None:
    """Test validation of invalid connector names."""
    result = create_connector_manifest_scaffold(
        ctx,
        connector_name="invalid-name",
        api_base_url="https://api.example.com",
        initial_stream_name="users",
        initial_stream_path="/users",
        authentication_type="NoAuth",
    )

    assert isinstance(result, str)
    assert result.startswith("ERROR:")
    assert "Input validation error" in result


def test_api_key_authentication(ctx) -> None:
    """Test manifest generation with API key authentication."""
    result = create_connector_manifest_scaffold(
        ctx,
        connector_name="source-test-api",
        api_base_url="https://api.example.com",
        initial_stream_name="users",
        initial_stream_path="/users",
        authentication_type="ApiKeyAuthenticator",
    )

    assert isinstance(result, str)
    assert not result.startswith("ERROR:")
    assert "Manifest scaffold created successfully" in result

    manifest_content = get_session_manifest_content(ctx.session_id)
    assert manifest_content is not None
    assert "ApiKeyAuthenticator" in manifest_content
    assert "api_key" in manifest_content


def test_pagination_configuration(ctx) -> None:
    """Test manifest generation includes commented pagination block."""
    result = create_connector_manifest_scaffold(
        ctx,
        connector_name="source-test-api",
        api_base_url="https://api.example.com",
        initial_stream_name="users",
        initial_stream_path="/users",
        authentication_type="NoAuth",
    )

    assert isinstance(result, str)
    assert not result.startswith("ERROR:")
    assert "Manifest scaffold created successfully" in result

    manifest_content = get_session_manifest_content(ctx.session_id)
    assert manifest_content is not None
    assert "NoPagination" in manifest_content
    assert "# TODO: Uncomment and configure pagination when known" in manifest_content
    assert "# paginator:" in manifest_content
    assert "#   type: DefaultPaginator" in manifest_content


def test_todo_placeholders(ctx) -> None:
    """Test that TODO placeholders are included in the manifest."""
    result = create_connector_manifest_scaffold(
        ctx,
        connector_name="source-test-api",
        api_base_url="https://api.example.com",
        initial_stream_name="users",
        initial_stream_path="/users",
        authentication_type="NoAuth",
    )

    assert isinstance(result, str)
    assert not result.startswith("ERROR:")
    assert "Manifest scaffold created successfully" in result

    manifest_content = get_session_manifest_content(ctx.session_id)
    assert manifest_content is not None
    assert "TODO" in manifest_content

    manifest_lines = manifest_content.split("\n")
    yaml_content = [line for line in manifest_lines if not line.strip().startswith("#")]

    manifest = yaml.safe_load("\n".join(yaml_content))
    assert manifest["streams"][0]["primary_key"] == ["TODO"]


def test_all_generated_manifests_pass_validation(ctx) -> None:
    """Test that all generated manifests pass validation regardless of inputs."""
    for auth_type in [at.value for at in AuthenticationType]:
        set_session_manifest_content("", session_id=ctx.session_id)

        result = create_connector_manifest_scaffold(
            ctx,
            connector_name=f"source-test-{auth_type.lower().replace('authenticator', '').replace('auth', '').replace('_', '-')}",
            api_base_url="https://api.example.com",
            initial_stream_name="users",
            initial_stream_path="/users",
            authentication_type=auth_type,
        )

        assert isinstance(result, str), f"Expected string, got {type(result)}"
        assert not result.startswith("ERROR:"), f"Failed with auth_type={auth_type}: {result}"

        manifest_content = get_session_manifest_content(ctx.session_id)
        assert manifest_content is not None, (
            f"No manifest found in session for auth_type={auth_type}"
        )

        validation_result = validate_manifest(ctx, manifest=manifest_content)
        assert validation_result.is_valid, (
            f"Direct validation failed with auth_type={auth_type}: {validation_result.errors}"
        )


def test_dynamic_schema_loader_included(ctx) -> None:
    """Test that dynamic schema loader is included in generated manifests."""
    result = create_connector_manifest_scaffold(
        ctx,
        connector_name="source-test-api",
        api_base_url="https://api.example.com",
        initial_stream_name="users",
        initial_stream_path="/users",
        authentication_type="NoAuth",
    )

    assert isinstance(result, str)
    assert not result.startswith("ERROR:")
    assert "Manifest scaffold created successfully" in result

    manifest_content = get_session_manifest_content(ctx.session_id)
    assert manifest_content is not None
    assert "TODO" in manifest_content


def test_incremental_sync_todo_comments(ctx) -> None:
    """Test that incremental sync TODO comments are included."""
    result = create_connector_manifest_scaffold(
        ctx,
        connector_name="source-test-api",
        api_base_url="https://api.example.com",
        initial_stream_name="users",
        initial_stream_path="/users",
        authentication_type="NoAuth",
    )

    assert isinstance(result, str)
    assert not result.startswith("ERROR:")
    assert "Manifest scaffold created successfully" in result

    manifest_content = get_session_manifest_content(ctx.session_id)
    assert manifest_content is not None
    assert "DatetimeBasedCursor" in manifest_content
    assert "cursor_field" in manifest_content
    assert "# TODO: Uncomment and configure incremental sync" in manifest_content
