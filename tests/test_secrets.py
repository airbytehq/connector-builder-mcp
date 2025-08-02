"""Tests for secrets management functionality."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import connector_builder_mcp._secrets as secrets_module
from connector_builder_mcp._secrets import (
    DEFAULT_SECRETS_FILE,
    SECRETS_FILE_ENV_VAR,
    SecretsFileInfo,
    get_dotenv_path,
    get_secrets_file_path,
    hydrate_config,
    list_dotenv_secrets,
    load_secrets,
    populate_dotenv_missing_secrets_stubs,
    set_dotenv_path,
)


class TestSecretsFilePath:
    """Test getting the secrets file path from different sources."""

    def test_get_secrets_file_path_default(self):
        """Test default path when no tool setting or env var."""
        original_path = secrets_module._current_dotenv_path
        secrets_module._current_dotenv_path = None

        try:
            with patch.dict(os.environ, {}, clear=True):
                path = get_secrets_file_path()
                assert path == DEFAULT_SECRETS_FILE
        finally:
            secrets_module._current_dotenv_path = original_path

    def test_get_secrets_file_path_from_env_var(self):
        """Test path from environment variable."""
        original_path = secrets_module._current_dotenv_path
        secrets_module._current_dotenv_path = None

        try:
            test_path = "/custom/path/.env"
            with patch.dict(os.environ, {SECRETS_FILE_ENV_VAR: test_path}):
                path = get_secrets_file_path()
                assert path == test_path
        finally:
            secrets_module._current_dotenv_path = original_path

    def test_get_secrets_file_path_from_tool_setting(self):
        """Test path from tool setting takes priority."""
        original_path = secrets_module._current_dotenv_path

        try:
            tool_path = "/tool/path/.env"
            secrets_module._current_dotenv_path = tool_path

            env_path = "/env/path/.env"
            with patch.dict(os.environ, {SECRETS_FILE_ENV_VAR: env_path}):
                path = get_secrets_file_path()
                assert path == tool_path
        finally:
            secrets_module._current_dotenv_path = original_path


class TestSetDotenvPath:
    """Test setting dotenv path via tool."""

    def test_set_dotenv_path(self):
        """Test setting dotenv path creates file and returns absolute path."""
        original_path = secrets_module._current_dotenv_path

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                test_file = Path(temp_dir) / "test.env"

                result = set_dotenv_path(str(test_file))

                assert secrets_module._current_dotenv_path == str(test_file.resolve())
                assert test_file.exists()
                assert f"Dotenv path set to: {test_file.resolve()}" in result
        finally:
            secrets_module._current_dotenv_path = original_path


class TestLoadSecrets:
    """Test loading secrets from dotenv files."""

    def test_load_secrets_file_not_exists(self):
        """Test loading from non-existent file returns empty dict."""
        original_path = secrets_module._current_dotenv_path

        try:
            secrets_module._current_dotenv_path = "/nonexistent/file.env"
            secrets = load_secrets()
            assert secrets == {}
        finally:
            secrets_module._current_dotenv_path = original_path

    def test_load_secrets_existing_file(self):
        """Test loading from existing file with secrets."""
        original_path = secrets_module._current_dotenv_path

        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
                f.write("CREDENTIALS_PASSWORD=secret123\n")
                f.write("API_TOKEN=token456\n")
                f.flush()

                secrets_module._current_dotenv_path = f.name
                secrets = load_secrets()

                assert secrets == {"CREDENTIALS_PASSWORD": "secret123", "API_TOKEN": "token456"}

                Path(f.name).unlink()
        finally:
            secrets_module._current_dotenv_path = original_path


class TestHydrateConfig:
    """Test config hydration with secrets."""

    def test_hydrate_config_no_secrets(self):
        """Test hydration with no secrets available."""
        config = {"host": "localhost", "credentials": {"username": "user"}}

        with patch("connector_builder_mcp._secrets.load_secrets", return_value={}):
            result = hydrate_config(config)
            assert result == config

    def test_hydrate_config_with_secrets(self):
        """Test hydration with secrets using naming convention."""
        config = {"host": "localhost", "credentials": {"username": "user"}, "oauth": {}}

        secrets = {
            "API_KEY": "secret123",
            "CREDENTIALS_PASSWORD": "pass456",
            "OAUTH_CLIENT_SECRET": "oauth789",
        }

        with patch("connector_builder_mcp._secrets.load_secrets", return_value=secrets):
            result = hydrate_config(config)

            expected = {
                "host": "localhost",
                "api_key": "secret123",
                "credentials": {"username": "user", "password": "pass456"},
                "oauth": {"client_secret": "oauth789"},
            }
            assert result == expected

    def test_hydrate_config_simple_keys(self):
        """Test hydration with simple environment variable names."""
        config = {"host": "localhost"}
        secrets = {"TOKEN": "token123", "URL": "https://api.example.com"}

        with patch("connector_builder_mcp._secrets.load_secrets", return_value=secrets):
            result = hydrate_config(config)

            expected = {"host": "localhost", "token": "token123", "url": "https://api.example.com"}
            assert result == expected

    def test_hydrate_config_ignores_comment_values(self):
        """Test that comment values (starting with #) are ignored."""
        config = {"host": "localhost"}
        secrets = {"API_KEY": "# TODO: Set actual value for API_KEY", "TOKEN": "real_token_value"}

        with patch("connector_builder_mcp._secrets.load_secrets", return_value=secrets):
            result = hydrate_config(config)

            expected = {"host": "localhost", "token": "real_token_value"}
            assert result == expected

    def test_hydrate_config_empty_config(self):
        """Test hydration with empty config."""
        result = hydrate_config({})
        assert result == {}

    def test_hydrate_config_none_config(self):
        """Test hydration with None config."""
        result = hydrate_config(None)
        assert result is None

    def test_hydrate_config_overwrites_existing_values(self):
        """Test that secrets overwrite existing config values."""
        config = {"api_key": "old_value", "credentials": {"password": "old_password"}}

        secrets = {"API_KEY": "new_secret", "CREDENTIALS_PASSWORD": "new_password"}

        with patch("connector_builder_mcp._secrets.load_secrets", return_value=secrets):
            result = hydrate_config(config)

            expected = {"api_key": "new_secret", "credentials": {"password": "new_password"}}
            assert result == expected


class TestListDotenvSecrets:
    """Test listing secrets without exposing values."""

    def test_list_dotenv_secrets_no_file(self):
        """Test listing when secrets file doesn't exist."""
        original_path = secrets_module._current_dotenv_path

        try:
            secrets_module._current_dotenv_path = "/nonexistent/file.env"
            result = list_dotenv_secrets()

            assert isinstance(result, SecretsFileInfo)
            assert result.exists is False
            assert result.secrets == []
            assert "/nonexistent/file.env" in result.file_path
        finally:
            secrets_module._current_dotenv_path = original_path

    def test_list_dotenv_secrets_with_file(self):
        """Test listing secrets from existing file."""
        original_path = secrets_module._current_dotenv_path

        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
                f.write("CREDENTIALS_PASSWORD=secret123\n")
                f.write("EMPTY_KEY=\n")
                f.write("API_TOKEN=token456\n")
                f.flush()

                secrets_module._current_dotenv_path = f.name
                result = list_dotenv_secrets()

                assert isinstance(result, SecretsFileInfo)
                assert result.exists is True
                assert len(result.secrets) == 3

                secret_keys = {s.key for s in result.secrets}
                assert secret_keys == {"CREDENTIALS_PASSWORD", "EMPTY_KEY", "API_TOKEN"}

                for secret in result.secrets:
                    if secret.key == "EMPTY_KEY":
                        assert secret.is_set is False
                    else:
                        assert secret.is_set is True

                Path(f.name).unlink()
        finally:
            secrets_module._current_dotenv_path = original_path


class TestPopulateDotenvMissingSecretsStubs:
    """Test adding secret stubs."""

    def test_populate_dotenv_missing_secrets_stubs_legacy_mode(self):
        """Test adding a secret stub using legacy single key mode."""
        original_path = secrets_module._current_dotenv_path

        try:
            with tempfile.NamedTemporaryFile(suffix=".env", delete=False) as f:
                secrets_module._current_dotenv_path = f.name

                result = populate_dotenv_missing_secrets_stubs(
                    secret_key="CREDENTIALS_PASSWORD", description="Password for API authentication"
                )

                assert "Added 1 secret stub(s)" in result
                assert "CREDENTIALS_PASSWORD" in result
                assert f.name in result

                with open(f.name) as file:
                    content = file.read()
                    assert "CREDENTIALS_PASSWORD=" in content
                    assert "TODO: Set actual value for CREDENTIALS_PASSWORD" in content
                    assert "Password for API authentication" in content

                Path(f.name).unlink()
        finally:
            secrets_module._current_dotenv_path = original_path

    def test_populate_dotenv_missing_secrets_stubs_config_paths(self):
        """Test adding secret stubs using config paths."""
        original_path = secrets_module._current_dotenv_path

        try:
            with tempfile.NamedTemporaryFile(suffix=".env", delete=False) as f:
                secrets_module._current_dotenv_path = f.name

                result = populate_dotenv_missing_secrets_stubs(
                    config_paths=["credentials.password", "oauth.client_secret"],
                    description="API authentication secrets",
                )

                assert "Added 2 secret stub(s)" in result
                assert "CREDENTIALS_PASSWORD" in result
                assert "OAUTH_CLIENT_SECRET" in result

                with open(f.name) as file:
                    content = file.read()
                    assert "CREDENTIALS_PASSWORD=" in content
                    assert "OAUTH_CLIENT_SECRET=" in content
                    assert "Secret for credentials.password" in content
                    assert "Secret for oauth.client_secret" in content

                Path(f.name).unlink()
        finally:
            secrets_module._current_dotenv_path = original_path

    def test_populate_dotenv_missing_secrets_stubs_manifest_mode(self):
        """Test adding secret stubs from manifest analysis."""
        original_path = secrets_module._current_dotenv_path

        try:
            with tempfile.NamedTemporaryFile(suffix=".env", delete=False) as f:
                secrets_module._current_dotenv_path = f.name

                manifest = {
                    "spec": {
                        "connection_specification": {
                            "properties": {
                                "api_token": {
                                    "type": "string",
                                    "airbyte_secret": True,
                                    "description": "API token for authentication",
                                },
                                "username": {"type": "string", "airbyte_secret": False},
                                "client_secret": {"type": "string", "airbyte_secret": True},
                            }
                        }
                    }
                }

                result = populate_dotenv_missing_secrets_stubs(manifest=manifest)

                assert "Added 2 secret stub(s)" in result
                assert "API_TOKEN" in result
                assert "CLIENT_SECRET" in result
                assert "username" not in result  # Should not include non-secret fields

                with open(f.name) as file:
                    content = file.read()
                    assert "API_TOKEN=" in content
                    assert "CLIENT_SECRET=" in content
                    assert "API token for authentication" in content

                Path(f.name).unlink()
        finally:
            secrets_module._current_dotenv_path = original_path

    def test_populate_dotenv_missing_secrets_stubs_combined_mode(self):
        """Test adding secret stubs using both manifest and config paths."""
        original_path = secrets_module._current_dotenv_path

        try:
            with tempfile.NamedTemporaryFile(suffix=".env", delete=False) as f:
                secrets_module._current_dotenv_path = f.name

                manifest = {
                    "spec": {
                        "connection_specification": {
                            "properties": {"api_token": {"type": "string", "airbyte_secret": True}}
                        }
                    }
                }

                result = populate_dotenv_missing_secrets_stubs(
                    manifest=manifest, config_paths=["credentials.password", "oauth.refresh_token"]
                )

                assert "Added 3 secret stub(s)" in result
                assert "API_TOKEN" in result
                assert "CREDENTIALS_PASSWORD" in result
                assert "OAUTH_REFRESH_TOKEN" in result

                with open(f.name) as file:
                    content = file.read()
                    assert "API_TOKEN=" in content
                    assert "CREDENTIALS_PASSWORD=" in content
                    assert "OAUTH_REFRESH_TOKEN=" in content

                Path(f.name).unlink()
        finally:
            secrets_module._current_dotenv_path = original_path

    def test_populate_dotenv_missing_secrets_stubs_no_args(self):
        """Test error when no arguments provided."""
        result = populate_dotenv_missing_secrets_stubs()
        assert "Error: Must provide either manifest, config_paths, or secret_key" in result

    def test_populate_dotenv_missing_secrets_stubs_empty_manifest(self):
        """Test with manifest that has no secrets."""
        original_path = secrets_module._current_dotenv_path

        try:
            with tempfile.NamedTemporaryFile(suffix=".env", delete=False) as f:
                secrets_module._current_dotenv_path = f.name

                manifest = {
                    "spec": {
                        "connection_specification": {
                            "properties": {"username": {"type": "string", "airbyte_secret": False}}
                        }
                    }
                }

                result = populate_dotenv_missing_secrets_stubs(manifest=manifest)
                assert "No secrets found to add" in result

                Path(f.name).unlink()
        finally:
            secrets_module._current_dotenv_path = original_path


class TestGetDotenvPath:
    """Test getting secrets file path for user reference."""

    def test_get_dotenv_path(self):
        """Test getting absolute path for user."""
        original_path = secrets_module._current_dotenv_path

        try:
            test_path = "relative/path/.env"
            secrets_module._current_dotenv_path = test_path

            result = get_dotenv_path()

            assert result == str(Path(test_path).absolute())
        finally:
            secrets_module._current_dotenv_path = original_path
