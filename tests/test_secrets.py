"""Tests for secrets management functionality."""

import os
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


def test_hydrate_config_no_dotenv_file_uris():
    """Test hydration with no dotenv file uris returns config unchanged."""
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
        absolute_path = str(Path(f.name).resolve())
        result = populate_dotenv_missing_secrets_stubs(
            absolute_path,
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
        absolute_path = str(Path(f.name).resolve())
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
        result = populate_dotenv_missing_secrets_stubs(absolute_path, manifest=manifest_yaml)

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
        absolute_path = str(Path(f.name).resolve())
        manifest = {
            "spec": {
                "connection_specification": {
                    "properties": {"api_token": {"type": "string", "airbyte_secret": True}}
                }
            }
        }

        manifest_yaml = yaml.dump(manifest)
        result = populate_dotenv_missing_secrets_stubs(
            absolute_path,
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


def test_populate_dotenv_missing_secrets_stubs_relative_path():
    """Test error when relative path is provided."""
    result = populate_dotenv_missing_secrets_stubs("relative/path/.env", config_paths="api_key")
    assert "Validation failed" in result
    assert "must be absolute" in result


def test_populate_dotenv_missing_secrets_stubs_collision_detection():
    """Test collision detection when secrets already exist."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write("api_token=existing_value\n")
        f.write("empty_secret=\n")
        f.write("comment_secret=# TODO: Set actual value for comment_secret\n")
        f.flush()

        absolute_path = str(Path(f.name).resolve())
        result = populate_dotenv_missing_secrets_stubs(
            absolute_path,
            config_paths="api_token,new_secret",
        )

        assert "Error: Cannot create stubs for secrets that already exist: api_token" in result
        assert "Existing secrets in file:" in result
        assert "api_token(set)" in result
        assert "empty_secret(unset)" in result
        assert "comment_secret(unset)" in result

        Path(f.name).unlink()


def test_populate_dotenv_missing_secrets_stubs_no_collision():
    """Test successful addition when no collisions exist."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write("existing_secret=value\n")
        f.flush()

        absolute_path = str(Path(f.name).resolve())
        result = populate_dotenv_missing_secrets_stubs(
            absolute_path,
            config_paths="new_secret1,new_secret2",
        )

        assert "Added 2 secret stub(s)" in result
        assert "new_secret1" in result
        assert "new_secret2" in result

        with open(f.name) as file:
            content = file.read()
            assert "existing_secret=value" in content  # Original content preserved
            assert "new_secret1=" in content
            assert "new_secret2=" in content
            assert "TODO: Set actual value for new_secret1" in content
            assert "TODO: Set actual value for new_secret2" in content

        Path(f.name).unlink()


def test_populate_dotenv_missing_secrets_stubs_empty_manifest():
    """Test with manifest that has no secrets."""
    with tempfile.NamedTemporaryFile(suffix=".env", delete=False) as f:
        absolute_path = str(Path(f.name).resolve())
        manifest = {
            "spec": {
                "connection_specification": {
                    "properties": {"username": {"type": "string", "airbyte_secret": False}}
                }
            }
        }

        manifest_yaml = yaml.dump(manifest)
        result = populate_dotenv_missing_secrets_stubs(absolute_path, manifest=manifest_yaml)
        assert "No secrets found to add" in result

        Path(f.name).unlink()


def test_load_secrets_comma_separated_string():
    """Test loading from comma-separated string of file paths."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f1:
        f1.write("api_key=secret1\n")
        f1.flush()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f2:
            f2.write("token=secret2\n")
            f2.flush()

            secrets = load_secrets(f"{f1.name},{f2.name}")

            assert secrets == {"api_key": "secret1", "token": "secret2"}

            Path(f1.name).unlink()
            Path(f2.name).unlink()


def test_load_secrets_list_of_files():
    """Test loading from list of file paths."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f1:
        f1.write("api_key=secret1\n")
        f1.flush()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f2:
            f2.write("token=secret2\n")
            f2.flush()

            secrets = load_secrets([f1.name, f2.name])

            assert secrets == {"api_key": "secret1", "token": "secret2"}

            Path(f1.name).unlink()
            Path(f2.name).unlink()


@patch("connector_builder_mcp._secrets.privatebin.get")
@patch("connector_builder_mcp._secrets.os.getenv")
def test_load_secrets_privatebin_url_success(mock_getenv, mock_privatebin_get):
    """Test loading from privatebin URL with password authentication."""
    mock_getenv.return_value = "test_password"
    mock_paste = mock_privatebin_get.return_value
    mock_paste.text = "api_key=secret123\ntoken=token456\n"

    secrets = load_secrets("https://privatebin.net/?abc123#testpassphrase")

    assert secrets == {"api_key": "secret123", "token": "token456"}
    mock_getenv.assert_called_with("PRIVATEBIN_PASSWORD")
    mock_privatebin_get.assert_called_with(
        "https://privatebin.net/?abc123#testpassphrase", password="test_password"
    )


@patch("connector_builder_mcp._secrets.os.getenv")
def test_load_secrets_privatebin_url_no_password(mock_getenv):
    """Test loading from privatebin URL without PRIVATEBIN_PASSWORD fails."""
    mock_getenv.return_value = None

    secrets = load_secrets("https://privatebin.net/?abc123#test_passphrase")

    assert secrets == {}
    mock_getenv.assert_called_with("PRIVATEBIN_PASSWORD")


@patch("connector_builder_mcp._secrets.os.getenv")
@patch("connector_builder_mcp._secrets.requests.get")
def test_load_secrets_privatebin_url_with_existing_password_param(mock_get, mock_getenv):
    """Test loading from privatebin URL with embedded password fails validation."""
    mock_getenv.return_value = "test_password"
    mock_response = mock_get.return_value
    mock_response.text = "api_key=secret123\n"
    mock_response.raise_for_status.return_value = None

    secrets = load_secrets("https://privatebin.net/abc123?password=existing_pass")

    assert secrets == {}


@patch("connector_builder_mcp._secrets.privatebin.get")
@patch("connector_builder_mcp._secrets.os.getenv")
def test_load_secrets_mixed_files_and_privatebin(mock_getenv, mock_privatebin_get):
    """Test loading from mix of local files and privatebin URLs."""
    mock_getenv.return_value = "test_password"
    mock_paste = mock_privatebin_get.return_value
    mock_paste.text = "privatebin_key=privatebin_secret\n"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write("local_key=local_secret\n")
        f.flush()

        secrets = load_secrets([f.name, "https://privatebin.net/?abc123#testpassphrase"])

        assert secrets == {"local_key": "local_secret", "privatebin_key": "privatebin_secret"}

        Path(f.name).unlink()


def test_list_dotenv_secrets_multiple_sources():
    """Test listing secrets from multiple sources."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f1:
        f1.write("api_key=secret1\n")
        f1.flush()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f2:
            f2.write("token=secret2\n")
            f2.flush()

            result = list_dotenv_secrets([f1.name, f2.name])

            assert isinstance(result, SecretsFileInfo)
            assert result.exists is True
            assert len(result.secrets) == 2

            secret_keys = {s.key for s in result.secrets}
            assert secret_keys == {"api_key", "token"}

            Path(f1.name).unlink()
            Path(f2.name).unlink()


@patch("connector_builder_mcp._secrets.os.getenv")
@patch("connector_builder_mcp._secrets._fetch_privatebin_content")
def test_list_dotenv_secrets_privatebin_url(mock_fetch, mock_getenv):
    """Test listing secrets from privatebin URL."""
    mock_getenv.return_value = "test_password"
    mock_fetch.return_value = "api_key=secret123\ntoken=\n"

    result = list_dotenv_secrets("https://privatebin.net/abc123")

    assert isinstance(result, SecretsFileInfo)
    assert result.exists is True
    assert len(result.secrets) == 2

    secret_keys = {s.key for s in result.secrets}
    assert secret_keys == {"api_key", "token"}

    for secret in result.secrets:
        if secret.key == "api_key":
            assert secret.is_set is True
        elif secret.key == "token":
            assert secret.is_set is False


@patch("connector_builder_mcp._secrets.os.getenv")
def test_populate_dotenv_missing_secrets_stubs_privatebin_url(mock_getenv):
    """Test populate stubs with privatebin URL returns instructions."""
    mock_getenv.return_value = "test_password"
    with patch("connector_builder_mcp._secrets.load_secrets") as mock_load:
        mock_load.return_value = {"existing_key": "value"}

        result = populate_dotenv_missing_secrets_stubs(
            "https://privatebin.net/abc123", config_paths="existing_key,missing_key"
        )

        assert "Existing secrets found: existing_key(set)" in result
        assert "Missing secrets: missing_key" in result
        assert "Instructions: Privatebin URLs are immutable" in result
        assert "Create a new privatebin with the missing secrets" in result
        assert "Set a password for the privatebin" in result
        assert "Use the new privatebin URL (HTTPS format is supported)" in result
        assert "Ensure PRIVATEBIN_PASSWORD environment variable is set" in result


@patch("connector_builder_mcp._secrets.os.getenv")
def test_populate_dotenv_missing_secrets_stubs_privatebin_all_present(mock_getenv):
    """Test populate stubs with privatebin URL when all secrets are present."""
    mock_getenv.return_value = "test_password"
    with patch("connector_builder_mcp._secrets.load_secrets") as mock_load:
        mock_load.return_value = {"key1": "value1", "key2": "value2"}

        result = populate_dotenv_missing_secrets_stubs(
            "https://privatebin.net/abc123", config_paths="key1,key2"
        )

        assert "All requested secrets are already present in the privatebin" in result
        assert "Instructions:" not in result


def test_populate_dotenv_missing_secrets_stubs_readonly_file():
    """Test populate stubs with read-only file path returns collision error first."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write("existing_key=value\n")
        f.flush()

        os.chmod(f.name, 0o444)

        try:
            result = populate_dotenv_missing_secrets_stubs(
                str(Path(f.name).resolve()), config_paths="existing_key,missing_key"
            )

            assert (
                "Error: Cannot create stubs for secrets that already exist: existing_key" in result
            )

        finally:
            os.chmod(f.name, 0o644)
            Path(f.name).unlink()


def test_validate_secrets_uris_absolute_path_valid():
    """Test validation passes for absolute paths."""
    from connector_builder_mcp._secrets import _validate_secrets_uris

    with tempfile.NamedTemporaryFile(suffix=".env", delete=False) as f:
        absolute_path = str(Path(f.name).resolve())
        errors = _validate_secrets_uris(absolute_path)
        assert errors == []
        Path(f.name).unlink()


def test_validate_secrets_uris_relative_path_invalid():
    """Test validation fails for relative paths."""
    from connector_builder_mcp._secrets import _validate_secrets_uris

    errors = _validate_secrets_uris("relative/path/.env")
    assert len(errors) == 1
    assert "must be absolute" in errors[0]
    assert "relative/path/.env" in errors[0]


@patch("connector_builder_mcp._secrets.os.getenv")
def test_validate_secrets_uris_privatebin_no_password(mock_getenv):
    """Test validation fails for privatebin URL without PRIVATEBIN_PASSWORD."""
    from connector_builder_mcp._secrets import _validate_secrets_uris

    mock_getenv.return_value = None
    errors = _validate_secrets_uris("https://privatebin.net/abc123")
    assert len(errors) == 1
    assert "requires PRIVATEBIN_PASSWORD environment variable" in errors[0]


@patch("connector_builder_mcp._secrets.os.getenv")
def test_validate_secrets_uris_privatebin_with_password_valid(mock_getenv):
    """Test validation passes for privatebin URL with PRIVATEBIN_PASSWORD set."""
    from connector_builder_mcp._secrets import _validate_secrets_uris

    mock_getenv.return_value = "test_password"
    errors = _validate_secrets_uris("https://privatebin.net/abc123")
    assert errors == []


@patch("connector_builder_mcp._secrets.os.getenv")
def test_validate_secrets_uris_privatebin_embedded_password_invalid(mock_getenv):
    """Test validation fails for privatebin URL with embedded password."""
    from connector_builder_mcp._secrets import _validate_secrets_uris

    mock_getenv.return_value = "test_password"
    errors = _validate_secrets_uris("https://privatebin.net/abc123?password=embedded")
    assert len(errors) == 1
    assert "contains embedded password" in errors[0]
    assert "not allowed for security reasons" in errors[0]


@patch("connector_builder_mcp._secrets.os.getenv")
def test_validate_secrets_uris_mixed_valid_invalid(mock_getenv):
    """Test validation with mix of valid and invalid URIs."""
    from connector_builder_mcp._secrets import _validate_secrets_uris

    mock_getenv.return_value = None

    with tempfile.NamedTemporaryFile(suffix=".env", delete=False) as f:
        absolute_path = str(Path(f.name).resolve())
        uris = [absolute_path, "relative/path/.env", "https://privatebin.net/abc123"]

        errors = _validate_secrets_uris(uris)
        assert len(errors) == 2
        assert any("must be absolute" in error for error in errors)
        assert any("requires PRIVATEBIN_PASSWORD" in error for error in errors)

        Path(f.name).unlink()


def test_load_secrets_validation_failure():
    """Test load_secrets returns empty dict when validation fails."""
    secrets = load_secrets("relative/path/.env")
    assert secrets == {}


def test_list_dotenv_secrets_validation_failure():
    """Test list_dotenv_secrets returns error info when validation fails."""
    result = list_dotenv_secrets("relative/path/.env")
    assert result.exists is False
    assert "Validation failed" in result.file_path
    assert "must be absolute" in result.file_path


def test_populate_dotenv_missing_secrets_stubs_validation_failure():
    """Test populate stubs returns validation error when validation fails."""
    result = populate_dotenv_missing_secrets_stubs("relative/path/.env", config_paths="api_key")
    assert "Validation failed" in result
    assert "must be absolute" in result


def test_populate_dotenv_missing_secrets_stubs_readonly_file_no_collision():
    """Test populate stubs with read-only file path returns write error when no collisions."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write("different_key=value\n")
        f.flush()

        os.chmod(f.name, 0o444)

        try:
            result = populate_dotenv_missing_secrets_stubs(
                str(Path(f.name).resolve()), config_paths="new_key"
            )

            assert "new_key" in result

        finally:
            os.chmod(f.name, 0o644)
            Path(f.name).unlink()
