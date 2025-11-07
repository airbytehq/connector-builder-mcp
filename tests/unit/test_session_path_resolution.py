"""Unit tests for session manifest path resolution with environment variable overrides."""

import os
from unittest.mock import patch

import pytest

from connector_builder_mcp.constants import (
    CONNECTOR_BUILDER_MCP_REMOTE_MODE,
    CONNECTOR_BUILDER_MCP_SESSION_DIR,
    CONNECTOR_BUILDER_MCP_SESSION_MANIFEST_PATH,
    CONNECTOR_BUILDER_MCP_SESSION_ROOT,
    CONNECTOR_BUILDER_MCP_SESSIONS_DIR,
)
from connector_builder_mcp.session_manifest import (
    _check_path_overrides_security,
    _is_remote_mode,
    _validate_absolute_path,
    resolve_session_manifest_path,
)


@pytest.mark.parametrize(
    "env_value,expected",
    [
        ("true", True),
        ("True", True),
        ("TRUE", True),
        ("1", True),
        ("yes", True),
        ("YES", True),
        ("false", False),
        ("False", False),
        ("0", False),
        ("no", False),
        ("", False),
        (None, False),
    ],
)
def test_is_remote_mode(env_value, expected):
    """Test remote mode detection from environment variable."""
    env = {CONNECTOR_BUILDER_MCP_REMOTE_MODE: env_value} if env_value is not None else {}
    with patch.dict(os.environ, env, clear=True):
        assert _is_remote_mode() == expected


@pytest.mark.parametrize(
    "path_str,should_succeed",
    [
        ("/absolute/path/to/file.yaml", True),
        ("/tmp/manifest.yaml", True),
        ("~/my/path/manifest.yaml", True),  # expanduser makes this absolute
        ("relative/path/file.yaml", False),
        ("./relative/path.yaml", False),
        ("../parent/path.yaml", False),
    ],
)
def test_validate_absolute_path(path_str, should_succeed, tmp_path):
    """Test absolute path validation."""
    if should_succeed:
        result = _validate_absolute_path(path_str, "TEST_VAR")
        assert result.is_absolute()
    else:
        with pytest.raises(ValueError, match="must be an absolute path"):
            _validate_absolute_path(path_str, "TEST_VAR")


@pytest.mark.parametrize(
    "override_var",
    [
        CONNECTOR_BUILDER_MCP_SESSION_MANIFEST_PATH,
        CONNECTOR_BUILDER_MCP_SESSION_DIR,
        CONNECTOR_BUILDER_MCP_SESSION_ROOT,
        CONNECTOR_BUILDER_MCP_SESSIONS_DIR,
    ],
)
def test_check_path_overrides_security_remote_mode(override_var, tmp_path):
    """Test that path overrides are rejected in remote mode."""
    env = {
        CONNECTOR_BUILDER_MCP_REMOTE_MODE: "true",
        override_var: str(tmp_path / "test"),
    }
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(RuntimeError, match="not allowed in remote mode"):
            _check_path_overrides_security()


def test_check_path_overrides_security_stdio_mode(tmp_path):
    """Test that path overrides are allowed in STDIO mode."""
    env = {
        CONNECTOR_BUILDER_MCP_REMOTE_MODE: "false",
        CONNECTOR_BUILDER_MCP_SESSION_MANIFEST_PATH: str(tmp_path / "manifest.yaml"),
    }
    with patch.dict(os.environ, env, clear=True):
        _check_path_overrides_security()


@pytest.mark.parametrize(
    "env_overrides,expected_path_suffix",
    [
        (
            {CONNECTOR_BUILDER_MCP_SESSION_MANIFEST_PATH: "/custom/manifest.yaml"},
            "/custom/manifest.yaml",
        ),
        (
            {CONNECTOR_BUILDER_MCP_SESSION_DIR: "/custom/session"},
            "/custom/session/manifest.yaml",
        ),
        (
            {CONNECTOR_BUILDER_MCP_SESSION_ROOT: "/custom/root"},
            None,  # Will check for hash in path
        ),
        (
            {CONNECTOR_BUILDER_MCP_SESSIONS_DIR: "/custom/legacy"},
            None,  # Will check for hash in path
        ),
        ({}, None),
    ],
)
def test_resolve_session_manifest_path_precedence(env_overrides, expected_path_suffix, tmp_path):
    """Test path resolution precedence hierarchy."""
    session_id = "test-session-123"

    abs_overrides = {}
    for key, value in env_overrides.items():
        if value.startswith("/custom"):
            abs_overrides[key] = str(tmp_path / value.lstrip("/"))
        else:
            abs_overrides[key] = value

    with patch.dict(os.environ, abs_overrides, clear=True):
        result = resolve_session_manifest_path(session_id)

        if expected_path_suffix:
            if expected_path_suffix == "/custom/manifest.yaml":
                assert str(result).endswith("custom/manifest.yaml")
            elif expected_path_suffix == "/custom/session/manifest.yaml":
                assert str(result).endswith("custom/session/manifest.yaml")
        else:
            assert "manifest.yaml" in str(result)
            parts = result.parts
            assert any(len(part) == 64 and all(c in "0123456789abcdef" for c in part) for part in parts)


def test_resolve_session_manifest_path_precedence_warnings(tmp_path, caplog):
    """Test that lower-precedence variables trigger warnings when ignored."""
    session_id = "test-session-123"

    env = {
        CONNECTOR_BUILDER_MCP_SESSION_MANIFEST_PATH: str(tmp_path / "manifest.yaml"),
        CONNECTOR_BUILDER_MCP_SESSION_DIR: str(tmp_path / "session"),
        CONNECTOR_BUILDER_MCP_SESSION_ROOT: str(tmp_path / "root"),
        CONNECTOR_BUILDER_MCP_SESSIONS_DIR: str(tmp_path / "legacy"),
    }

    with patch.dict(os.environ, env, clear=True):
        resolve_session_manifest_path(session_id)

        assert any("is ignored" in record.message for record in caplog.records)


def test_resolve_session_manifest_path_relative_path_rejected(tmp_path):
    """Test that relative paths are rejected."""
    session_id = "test-session-123"

    env = {CONNECTOR_BUILDER_MCP_SESSION_MANIFEST_PATH: "relative/path/manifest.yaml"}

    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(ValueError, match="must be an absolute path"):
            resolve_session_manifest_path(session_id)


def test_resolve_session_manifest_path_expanduser(tmp_path):
    """Test that ~ is expanded in paths."""
    session_id = "test-session-123"

    env = {CONNECTOR_BUILDER_MCP_SESSION_MANIFEST_PATH: "~/test/manifest.yaml"}

    with patch.dict(os.environ, env, clear=True):
        result = resolve_session_manifest_path(session_id)
        assert result.is_absolute()
        assert "~" not in str(result)
