"""Tests for secrets management functionality."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import yaml

from connector_builder_mcp._secrets import (
    SecretsFileInfo,
    hydrate_config,
    list_dotenv_secrets,
    load_secrets,
    populate_dotenv_missing_secrets_stubs,
)


def test_load_secrets_file_not_exists():
    """Test loading from non-existent file returns empty dict."""
    secrets = load_secrets("/nonexistent/file.env")
    assert secrets == {}


def test_load_secrets_existing_file():
    """Test loading from existing file with secrets."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write("credentials.password=secret123\n")
        f.write("api_token=token456\n")
        f.flush()

        secrets = load_secrets(f.name)

        assert secrets == {"credentials.password": "secret123", "api_token": "token456"}

        Path(f.name).unlink()


def test_hydrate_config_no_dotenv_path():
    """Test hydration with no dotenv path returns config unchanged."""
    config = {"host": "localhost", "credentials": {"username": "user"}}
    result = hydrate_config(config)
    assert result == config


def test_hydrate_config_no_secrets():
    """Test hydration with no secrets available."""
    config = {"host": "localhost", "credentials": {"username": "user"}}

    with patch("connector_builder_mcp._secrets.load_secrets", return_value={}):
        result = hydrate_config(config, "/path/to/.env")
        assert result == config


def test_hydrate_config_with_secrets():
    """Test hydration with secrets using dot notation, including simple keys."""
    config = {"host": "localhost", "credentials": {"username": "user"}, "oauth": {}}

    secrets = {
        "api_key": "secret123",
        "credentials.password": "pass456",
        "oauth.client_secret": "oauth789",
        "token": "token123",
        "url": "https://api.example.com",
    }

    with patch("connector_builder_mcp._secrets.load_secrets", return_value=secrets):
        result = hydrate_config(config, "/path/to/.env")

        expected = {
            "host": "localhost",
            "api_key": "secret123",
            "token": "token123",
            "url": "https://api.example.com",
            "credentials": {"username": "user", "password": "pass456"},
            "oauth": {"client_secret": "oauth789"},
        }
        assert result == expected


def test_hydrate_config_ignores_comment_values():
    """Test that comment values (starting with #) are ignored."""
    config = {"host": "localhost"}
    secrets = {"api_key": "# TODO: Set actual value for api_key", "token": "real_token_value"}

    with patch("connector_builder_mcp._secrets.load_secrets", return_value=secrets):
        result = hydrate_config(config, "/path/to/.env")

        expected = {"host": "localhost", "token": "real_token_value"}
        assert result == expected


def test_hydrate_config_overwrites_existing_values():
    """Test that secrets overwrite existing config values."""
    config = {"api_key": "old_value", "credentials": {"password": "old_password"}}

    secrets = {"api_key": "new_secret", "credentials.password": "new_password"}

    with patch("connector_builder_mcp._secrets.load_secrets", return_value=secrets):
        result = hydrate_config(config, "/path/to/.env")

        expected = {"api_key": "new_secret", "credentials": {"password": "new_password"}}
        assert result == expected


def test_list_dotenv_secrets_no_file():
    """Test listing when secrets file doesn't exist."""
    result = list_dotenv_secrets("/nonexistent/file.env")

    assert isinstance(result, SecretsFileInfo)
    assert result.exists is False
    assert result.secrets == []
    assert "/nonexistent/file.env" in result.file_path


def test_list_dotenv_secrets_with_file():
    """Test listing secrets from existing file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write("credentials.password=secret123\n")
        f.write("empty_key=\n")
        f.write("api_token=token456\n")
        f.flush()

        result = list_dotenv_secrets(f.name)

        assert isinstance(result, SecretsFileInfo)
        assert result.exists is True
        assert len(result.secrets) == 3

        secret_keys = {s.key for s in result.secrets}
        assert secret_keys == {"credentials.password", "empty_key", "api_token"}

        for secret in result.secrets:
            if secret.key == "empty_key":
                assert secret.is_set is False
            else:
                assert secret.is_set is True

        Path(f.name).unlink()


def test_populate_dotenv_missing_secrets_stubs_config_paths():
    """Test adding secret stubs using config paths."""
    with tempfile.NamedTemporaryFile(suffix=".env", delete=False) as f:
        result = populate_dotenv_missing_secrets_stubs(
            f.name,
            config_paths="credentials.password,oauth.client_secret",
        )

        assert "Added 2 secret stub(s)" in result
        assert "credentials.password" in result
        assert "oauth.client_secret" in result

        with open(f.name) as file:
            content = file.read()
            assert "credentials.password=" in content
            assert "oauth.client_secret=" in content
            assert "TODO: Set actual value for credentials.password" in content
            assert "TODO: Set actual value for oauth.client_secret" in content

        Path(f.name).unlink()


def test_populate_dotenv_missing_secrets_stubs_manifest_mode():
    """Test adding secret stubs from manifest analysis."""
    with tempfile.NamedTemporaryFile(suffix=".env", delete=False) as f:
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

        manifest_yaml = yaml.dump(manifest)
        result = populate_dotenv_missing_secrets_stubs(f.name, manifest=manifest_yaml)

        assert "Added 2 secret stub(s)" in result
        assert "api_token" in result
        assert "client_secret" in result
        assert "username" not in result

        with open(f.name) as file:
            content = file.read()
            assert "api_token=" in content
            assert "client_secret=" in content
            assert "TODO: Set actual value for api_token" in content
            assert "TODO: Set actual value for client_secret" in content

        Path(f.name).unlink()


def test_populate_dotenv_missing_secrets_stubs_combined_mode():
    """Test adding secret stubs using both manifest and config paths."""
    with tempfile.NamedTemporaryFile(suffix=".env", delete=False) as f:
        manifest = {
            "spec": {
                "connection_specification": {
                    "properties": {"api_token": {"type": "string", "airbyte_secret": True}}
                }
            }
        }

        manifest_yaml = yaml.dump(manifest)
        result = populate_dotenv_missing_secrets_stubs(
            f.name,
            manifest=manifest_yaml,
            config_paths="credentials.password,oauth.refresh_token",
        )

        assert "Added 3 secret stub(s)" in result
        assert "api_token" in result
        assert "credentials.password" in result
        assert "oauth.refresh_token" in result

        with open(f.name) as file:
            content = file.read()
            assert "api_token=" in content
            assert "credentials.password=" in content
            assert "oauth.refresh_token=" in content
            assert "TODO: Set actual value for api_token" in content
            assert "TODO: Set actual value for credentials.password" in content
            assert "TODO: Set actual value for oauth.refresh_token" in content

        Path(f.name).unlink()


def test_populate_dotenv_missing_secrets_stubs_no_args():
    """Test error when no arguments provided."""
    result = populate_dotenv_missing_secrets_stubs("/path/to/.env")
    assert "Error: Must provide either manifest or config_paths" in result


def test_populate_dotenv_missing_secrets_stubs_empty_manifest():
    """Test with manifest that has no secrets."""
    with tempfile.NamedTemporaryFile(suffix=".env", delete=False) as f:
        manifest = {
            "spec": {
                "connection_specification": {
                    "properties": {"username": {"type": "string", "airbyte_secret": False}}
                }
            }
        }

        manifest_yaml = yaml.dump(manifest)
        result = populate_dotenv_missing_secrets_stubs(f.name, manifest=manifest_yaml)
        assert "No secrets found to add" in result

        Path(f.name).unlink()
