"""Tests for secrets management functionality."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from connector_builder_mcp.mcp.secrets_config import (
    SecretsFileInfo,
    _cast_secrets_to_types,
    _cast_value_to_type,
    _get_schema_for_path,
    _load_secrets,
    hydrate_config,
    list_dotenv_secrets,
    populate_dotenv_missing_secrets_stubs,
)


@pytest.fixture
def dummy_dotenv_file_expected_dict() -> dict[str, str | dict[str, str]]:
    """Create a dummy .env file dictionary for testing."""
    return {
        "api_key": "example_api_key",
        "credentials": {
            "password": "example_password",
        },
        "oauth": {
            "client_secret": "example_client_secret",
        },
        "token": "example_token",
        "url": "https://example.com",
    }


@pytest.fixture
def dummy_dotenv_file_keypairs() -> dict[str, str]:
    """Create a dummy .env file dictionary for testing."""
    return {
        "api_key": "example_api_key",
        "credentials.password": "example_password",
        "oauth.client_secret": "example_client_secret",
        "token": "example_token",
        "url": "https://example.com",
        "empty_key": "",
        "comment_secret": "# TODO: Set actual value for comment_secret",
    }


# Pytest fixture for a dummy dotenv file
@pytest.fixture
def dummy_dotenv_file(tmp_path, dummy_dotenv_file_keypairs) -> str:
    """Create a dummy .env file for testing."""
    file_path = tmp_path / "dummy.env"
    file_path.write_text("\n".join([f"{k}={v}" for k, v in dummy_dotenv_file_keypairs.items()]))
    return str(file_path)


def test_load_secrets_file_not_exists():
    """Test loading from non-existent file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        _load_secrets("/nonexistent/file.env")


def test_load_secrets_existing_file():
    """Test loading from existing file with secrets."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write("credentials.password=secret123\n")
        f.write("api_token=token456\n")
        f.flush()

        secrets = _load_secrets(f.name)

        assert secrets == {
            "credentials": {"password": "secret123"},
            "api_token": "token456",
        }

        Path(f.name).unlink()


def test_hydrate_config_no_dotenv_file_uris():
    """Test hydration with no dotenv file uris returns config unchanged."""
    config = {"host": "localhost", "credentials": {"username": "user"}}
    result = hydrate_config(config)
    assert result == config


def test_hydrate_with_no_config(dummy_dotenv_file, dummy_dotenv_file_expected_dict):
    """Test hydration with no dotenv file uris returns config unchanged."""
    result = hydrate_config({}, dummy_dotenv_file)
    assert result == dummy_dotenv_file_expected_dict


def test_hydrate_config_no_secrets():
    """Test hydration with no secrets available."""
    config = {"host": "localhost", "credentials": {"username": "user"}}

    with patch("connector_builder_mcp.mcp.secrets_config._load_secrets", return_value={}):
        result = hydrate_config(config, "/path/to/.env")
        assert result == config


def test_hydrate_config_with_secrets(dummy_dotenv_file):
    config = {
        "host": "localhost",
        "credentials": {"username": "user"},
        "oauth": {},
    }
    result = hydrate_config(config, dummy_dotenv_file)
    expected = {
        "host": "localhost",
        "api_key": "example_api_key",
        "token": "example_token",
        "url": "https://example.com",
        "credentials": {"username": "user", "password": "example_password"},
        "oauth": {"client_secret": "example_client_secret"},
    }
    assert result == expected


def test_hydrate_config_ignores_comment_values(dummy_dotenv_file):
    config = {"host": "localhost"}
    result = hydrate_config(config, dummy_dotenv_file)
    # Only token should be hydrated, comment_secret should be ignored if logic is correct
    assert result["token"] == "example_token"


def test_hydrate_config_overwrites_existing_values(dummy_dotenv_file):
    config = {
        "api_key": "old_value",
        "credentials": {
            "password": "old_password",
        },
    }
    result = hydrate_config(
        config,
        dummy_dotenv_file,
    )
    assert result["api_key"] == "example_api_key"
    assert result["credentials"]["password"] == "example_password"


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

            secrets = _load_secrets(f"{f1.name},{f2.name}")

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

            secrets = _load_secrets([f1.name, f2.name])

            assert secrets == {"api_key": "secret1", "token": "secret2"}

            Path(f1.name).unlink()
            Path(f2.name).unlink()


@patch("connector_builder_mcp.mcp.secrets_config.privatebin.get")
@patch("connector_builder_mcp.mcp.secrets_config.os.getenv")
def test_load_secrets_privatebin_url_success(mock_getenv, mock_privatebin_get):
    """Test loading from privatebin URL with password authentication."""
    mock_getenv.return_value = "test_password"
    mock_paste = mock_privatebin_get.return_value
    mock_paste.text = "api_key=secret123\ntoken=token456\n"

    secrets = _load_secrets("https://privatebin.net/?abc123#testpassphrase")

    assert secrets == {"api_key": "secret123", "token": "token456"}
    mock_getenv.assert_called_with("PRIVATEBIN_PASSWORD")
    mock_privatebin_get.assert_called_with(
        "https://privatebin.net/?abc123#testpassphrase", password="test_password"
    )


@patch("connector_builder_mcp.mcp.secrets_config.os.getenv")
def test_load_secrets_privatebin_url_no_password(mock_getenv):
    """Test loading from privatebin URL without PRIVATEBIN_PASSWORD fails."""
    mock_getenv.return_value = None

    secrets = _load_secrets("https://privatebin.net/?abc123#test_passphrase")

    assert secrets == {}
    mock_getenv.assert_called_with("PRIVATEBIN_PASSWORD")


@patch("connector_builder_mcp.mcp.secrets_config.os.getenv")
@patch("connector_builder_mcp.mcp.secrets_config.requests.get")
def test_load_secrets_privatebin_url_with_existing_password_param(mock_get, mock_getenv):
    """Test loading from privatebin URL with embedded password fails validation."""
    mock_getenv.return_value = "test_password"
    mock_response = mock_get.return_value
    mock_response.text = "api_key=secret123\n"
    mock_response.raise_for_status.return_value = None

    secrets = _load_secrets("https://privatebin.net/abc123?password=existing_pass")

    assert secrets == {}


@patch("connector_builder_mcp.mcp.secrets_config.privatebin.get")
@patch("connector_builder_mcp.mcp.secrets_config.os.getenv")
def test_load_secrets_mixed_files_and_privatebin(mock_getenv, mock_privatebin_get):
    """Test loading from mix of local files and privatebin URLs."""
    mock_getenv.return_value = "test_password"
    mock_paste = mock_privatebin_get.return_value
    mock_paste.text = "privatebin_key=privatebin_secret\n"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write("local_key=local_secret\n")
        f.flush()

        secrets = _load_secrets([f.name, "https://privatebin.net/?abc123#testpassphrase"])

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


@patch("connector_builder_mcp.mcp.secrets_config.os.getenv")
@patch("connector_builder_mcp.mcp.secrets_config._fetch_privatebin_content")
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


@patch("connector_builder_mcp.mcp.secrets_config.os.getenv")
def test_populate_dotenv_missing_secrets_stubs_privatebin_url(mock_getenv):
    """Test populate stubs with privatebin URL returns instructions."""
    mock_getenv.return_value = "test_password"
    with patch("connector_builder_mcp.mcp.secrets_config._load_secrets") as mock_load:
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


@patch("connector_builder_mcp.mcp.secrets_config.os.getenv")
def test_populate_dotenv_missing_secrets_stubs_privatebin_all_present(mock_getenv):
    """Test populate stubs with privatebin URL when all secrets are present."""
    mock_getenv.return_value = "test_password"
    with patch("connector_builder_mcp.mcp.secrets_config._load_secrets") as mock_load:
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
    from connector_builder_mcp.mcp.secrets_config import _validate_secrets_uris

    with tempfile.NamedTemporaryFile(suffix=".env", delete=False) as f:
        absolute_path = str(Path(f.name).resolve())
        errors = _validate_secrets_uris(absolute_path)
        assert errors == []
        Path(f.name).unlink()


def test_validate_secrets_uris_relative_path_invalid():
    """Test validation fails for relative paths."""
    from connector_builder_mcp.mcp.secrets_config import _validate_secrets_uris

    errors = _validate_secrets_uris("relative/path/.env")
    assert len(errors) == 1
    assert "must be absolute" in errors[0]
    assert "relative/path/.env" in errors[0]


@patch("connector_builder_mcp.mcp.secrets_config.os.getenv")
def test_validate_secrets_uris_privatebin_no_password(mock_getenv):
    """Test validation fails for privatebin URL without PRIVATEBIN_PASSWORD."""
    from connector_builder_mcp.mcp.secrets_config import _validate_secrets_uris

    mock_getenv.return_value = None
    errors = _validate_secrets_uris("https://privatebin.net/abc123")
    assert len(errors) == 1
    assert "requires PRIVATEBIN_PASSWORD environment variable" in errors[0]


@patch("connector_builder_mcp.mcp.secrets_config.os.getenv")
def test_validate_secrets_uris_privatebin_with_password_valid(mock_getenv):
    """Test validation passes for privatebin URL with PRIVATEBIN_PASSWORD set."""
    from connector_builder_mcp.mcp.secrets_config import _validate_secrets_uris

    mock_getenv.return_value = "test_password"
    errors = _validate_secrets_uris("https://privatebin.net/abc123")
    assert errors == []


@patch("connector_builder_mcp.mcp.secrets_config.os.getenv")
def test_validate_secrets_uris_privatebin_embedded_password_invalid(mock_getenv):
    """Test validation fails for privatebin URL with embedded password."""
    from connector_builder_mcp.mcp.secrets_config import _validate_secrets_uris

    mock_getenv.return_value = "test_password"
    errors = _validate_secrets_uris("https://privatebin.net/abc123?password=embedded")
    assert len(errors) == 1
    assert "contains embedded password" in errors[0]
    assert "not allowed for security reasons" in errors[0]


@patch("connector_builder_mcp.mcp.secrets_config.os.getenv")
def test_validate_secrets_uris_mixed_valid_invalid(mock_getenv):
    """Test validation with mix of valid and invalid URIs."""
    from connector_builder_mcp.mcp.secrets_config import _validate_secrets_uris

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
    """Test _load_secrets returns empty dict when validation fails."""
    secrets = _load_secrets("relative/path/.env")
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


# ============================================================================
# Tests for Type Casting Functionality
# ============================================================================


@pytest.fixture
def sample_spec():
    """Sample connector spec for testing type casting."""
    return {
        "connection_specification": {
            "type": "object",
            "properties": {
                "api_key": {"type": "string"},
                "port": {"type": "integer"},
                "timeout": {"type": "number"},
                "enabled": {"type": "boolean"},
                "start_date": {"type": "string", "format": "date-time"},
                "credentials": {
                    "type": "object",
                    "properties": {
                        "password": {"type": "string"},
                        "user_id": {"type": "integer"},
                    },
                },
                "oauth": {
                    "type": "object",
                    "properties": {
                        "client_secret": {"type": "string"},
                        "refresh_token": {"type": "string"},
                        "nested": {
                            "type": "object",
                            "properties": {
                                "deep_value": {"type": "boolean"},
                            },
                        },
                    },
                },
            },
        }
    }


# Tests for _cast_value_to_type


@pytest.mark.parametrize(
    "value,schema_type,schema_format,expected",
    [
        # Happy path - integer
        ("123", "integer", None, 123),
        ("0", "integer", None, 0),
        ("-456", "integer", None, -456),
        # Happy path - number
        ("3.14", "number", None, 3.14),
        ("0.0", "number", None, 0.0),
        ("-2.5", "number", None, -2.5),
        ("123", "number", None, 123.0),
        # Happy path - boolean
        ("true", "boolean", None, True),
        ("True", "boolean", None, True),
        ("TRUE", "boolean", None, True),
        ("1", "boolean", None, True),
        ("yes", "boolean", None, True),
        ("false", "boolean", None, False),
        ("False", "boolean", None, False),
        ("FALSE", "boolean", None, False),
        ("0", "boolean", None, False),
        ("no", "boolean", None, False),
        # Happy path - string
        ("any_value", "string", None, "any_value"),
        ("123", "string", None, "123"),
        ("", "string", None, ""),
        # Happy path - array
        ('["a", "b", "c"]', "array", None, ["a", "b", "c"]),
        ("[1, 2, 3]", "array", None, [1, 2, 3]),
        ("[]", "array", None, []),
        # Happy path - object
        ('{"key": "value"}', "object", None, {"key": "value"}),
        ('{"nested": {"key": 123}}', "object", None, {"nested": {"key": 123}}),
        ("{}", "object", None, {}),
        # Edge cases - invalid casting (fallback to string)
        ("not_a_number", "integer", None, "not_a_number"),
        ("abc", "number", None, "abc"),
        ("maybe", "boolean", None, "maybe"),
        ("not_json", "array", None, "not_json"),
        ("also_not_json", "object", None, "also_not_json"),
        ("{invalid json}", "object", None, "{invalid json}"),
        ("[invalid, json]", "array", None, "[invalid, json]"),
        # Edge cases - empty string
        ("", "integer", None, ""),
        ("", "number", None, ""),
        ("", "boolean", None, ""),
        # Edge cases - whitespace
        ("  true  ", "boolean", None, True),
        # Edge cases - unknown type (fallback to string)
        ("value", "unknown_type", None, "value"),
        ("value", None, None, "value"),
    ],
)
def test_cast_value_to_type(value, schema_type, schema_format, expected):
    """Test _cast_value_to_type with various input types and values."""
    result = _cast_value_to_type(value, schema_type, schema_format)
    assert result == expected
    assert type(result) is type(expected)


def test_cast_value_to_type_array_returns_string_if_not_list():
    """Test that array type returns string if JSON doesn't parse to a list."""
    result = _cast_value_to_type('{"key": "value"}', "array", None)
    assert result == '{"key": "value"}'
    assert isinstance(result, str)


def test_cast_value_to_type_object_returns_string_if_not_dict():
    """Test that object type returns string if JSON doesn't parse to a dict."""
    result = _cast_value_to_type('["a", "b"]', "object", None)
    assert result == '["a", "b"]'
    assert isinstance(result, str)


# Tests for _get_schema_for_path


def test_get_schema_for_path_top_level_field(sample_spec):
    """Test extracting schema for top-level field."""
    schema_type, schema_format = _get_schema_for_path(sample_spec, "api_key")
    assert schema_type == "string"
    assert schema_format is None


def test_get_schema_for_path_with_format(sample_spec):
    """Test extracting schema with format specifier."""
    schema_type, schema_format = _get_schema_for_path(sample_spec, "start_date")
    assert schema_type == "string"
    assert schema_format == "date-time"


def test_get_schema_for_path_nested_field(sample_spec):
    """Test extracting schema for nested field."""
    schema_type, schema_format = _get_schema_for_path(sample_spec, "credentials.password")
    assert schema_type == "string"
    assert schema_format is None

    schema_type, schema_format = _get_schema_for_path(sample_spec, "credentials.user_id")
    assert schema_type == "integer"
    assert schema_format is None


def test_get_schema_for_path_deeply_nested_field(sample_spec):
    """Test extracting schema for deeply nested field."""
    schema_type, schema_format = _get_schema_for_path(sample_spec, "oauth.nested.deep_value")
    assert schema_type == "boolean"
    assert schema_format is None


def test_get_schema_for_path_nonexistent_field(sample_spec):
    """Test extracting schema for nonexistent field returns None."""
    schema_type, schema_format = _get_schema_for_path(sample_spec, "nonexistent")
    assert schema_type is None
    assert schema_format is None


def test_get_schema_for_path_nonexistent_nested_field(sample_spec):
    """Test extracting schema for nonexistent nested field returns None."""
    schema_type, schema_format = _get_schema_for_path(sample_spec, "credentials.nonexistent")
    assert schema_type is None
    assert schema_format is None


def test_get_schema_for_path_partial_path(sample_spec):
    """Test extracting schema stops at non-object intermediate field."""
    # api_key is a string, so we can't traverse further
    schema_type, schema_format = _get_schema_for_path(sample_spec, "api_key.subfield")
    assert schema_type is None
    assert schema_format is None


def test_get_schema_for_path_no_spec():
    """Test extracting schema with no spec returns None."""
    schema_type, schema_format = _get_schema_for_path(None, "api_key")
    assert schema_type is None
    assert schema_format is None


def test_get_schema_for_path_empty_spec():
    """Test extracting schema with empty spec returns None."""
    schema_type, schema_format = _get_schema_for_path({}, "api_key")
    assert schema_type is None
    assert schema_format is None


def test_get_schema_for_path_missing_properties():
    """Test extracting schema when properties key is missing."""
    spec = {"connection_specification": {"type": "object"}}
    schema_type, schema_format = _get_schema_for_path(spec, "api_key")
    assert schema_type is None
    assert schema_format is None


@pytest.mark.parametrize(
    "path,expected_type",
    [
        ("port", "integer"),
        ("timeout", "number"),
        ("enabled", "boolean"),
        ("api_key", "string"),
        ("credentials.user_id", "integer"),
        ("oauth.client_secret", "string"),
    ],
)
def test_get_schema_for_path_various_types(sample_spec, path, expected_type):
    """Test extracting schema for various field types."""
    schema_type, schema_format = _get_schema_for_path(sample_spec, path)
    assert schema_type == expected_type


# Tests for _cast_secrets_to_types


def test_cast_secrets_to_types_flat_dict(sample_spec):
    """Test casting secrets in a flat dictionary."""
    secrets = {
        "api_key": "my_key",
        "port": "8080",
        "enabled": "true",
    }

    result = _cast_secrets_to_types(secrets, sample_spec)

    assert result["api_key"] == "my_key"
    assert result["port"] == 8080
    assert isinstance(result["port"], int)
    assert result["enabled"] is True
    assert isinstance(result["enabled"], bool)


def test_cast_secrets_to_types_nested_dict(sample_spec):
    """Test casting secrets in a nested dictionary."""
    secrets = {
        "api_key": "my_key",
        "credentials": {
            "password": "secret",
            "user_id": "12345",
        },
        "oauth": {
            "client_secret": "oauth_secret",
        },
    }

    result = _cast_secrets_to_types(secrets, sample_spec)

    assert result["api_key"] == "my_key"
    assert result["credentials"]["password"] == "secret"
    assert result["credentials"]["user_id"] == 12345
    assert isinstance(result["credentials"]["user_id"], int)
    assert result["oauth"]["client_secret"] == "oauth_secret"


def test_cast_secrets_to_types_deeply_nested_dict(sample_spec):
    """Test casting secrets in a deeply nested dictionary."""
    secrets = {
        "oauth": {
            "nested": {
                "deep_value": "true",
            },
        },
    }

    result = _cast_secrets_to_types(secrets, sample_spec)

    assert result["oauth"]["nested"]["deep_value"] is True
    assert isinstance(result["oauth"]["nested"]["deep_value"], bool)


def test_cast_secrets_to_types_field_not_in_spec(sample_spec):
    """Test that fields not in spec remain as strings."""
    secrets = {
        "api_key": "my_key",
        "unknown_field": "123",
    }

    result = _cast_secrets_to_types(secrets, sample_spec)

    assert result["api_key"] == "my_key"
    assert result["unknown_field"] == "123"
    assert isinstance(result["unknown_field"], str)


def test_cast_secrets_to_types_invalid_value_fallback(sample_spec):
    """Test that invalid values fallback to strings."""
    secrets = {
        "port": "not_a_number",
        "enabled": "maybe",
    }

    result = _cast_secrets_to_types(secrets, sample_spec)

    assert result["port"] == "not_a_number"
    assert isinstance(result["port"], str)
    assert result["enabled"] == "maybe"
    assert isinstance(result["enabled"], str)


def test_cast_secrets_to_types_empty_dict(sample_spec):
    """Test casting an empty secrets dictionary."""
    result = _cast_secrets_to_types({}, sample_spec)
    assert result == {}


def test_cast_secrets_to_types_non_string_values(sample_spec):
    """Test that non-string values pass through unchanged."""
    secrets = {
        "api_key": "my_key",
        "port": 8080,  # Already an int
        "enabled": True,  # Already a bool
    }

    result = _cast_secrets_to_types(secrets, sample_spec)

    assert result["api_key"] == "my_key"
    assert result["port"] == 8080
    assert result["enabled"] is True


def test_cast_secrets_to_types_mixed_nested_structure(sample_spec):
    """Test casting a complex mixed nested structure."""
    secrets = {
        "api_key": "my_key",
        "port": "8080",
        "credentials": {
            "password": "secret",
            "user_id": "12345",
        },
        "unknown_nested": {
            "field": "value",
        },
    }

    result = _cast_secrets_to_types(secrets, sample_spec)

    assert result["api_key"] == "my_key"
    assert result["port"] == 8080
    assert result["credentials"]["user_id"] == 12345
    assert result["unknown_nested"]["field"] == "value"  # Unknown fields remain strings


# Integration Tests for hydrate_config with spec


def test_hydrate_config_with_spec_casts_types(sample_spec):
    """Test hydrate_config with spec performs type casting."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write("api_key=my_key\n")
        f.write("port=8080\n")
        f.write("enabled=true\n")
        f.write("credentials.user_id=12345\n")
        f.flush()

        config = {"host": "localhost"}
        result = hydrate_config(config, spec=sample_spec, dotenv_file_uris=f.name)

        assert result["api_key"] == "my_key"
        assert result["port"] == 8080
        assert isinstance(result["port"], int)
        assert result["enabled"] is True
        assert isinstance(result["enabled"], bool)
        assert result["credentials"]["user_id"] == 12345
        assert isinstance(result["credentials"]["user_id"], int)

        Path(f.name).unlink()


def test_hydrate_config_without_spec_no_casting(sample_spec):
    """Test hydrate_config without spec doesn't perform type casting."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write("api_key=my_key\n")
        f.write("port=8080\n")
        f.write("enabled=true\n")
        f.flush()

        config = {"host": "localhost"}
        result = hydrate_config(config, spec=None, dotenv_file_uris=f.name)

        # Without spec, all values remain strings
        assert result["api_key"] == "my_key"
        assert result["port"] == "8080"
        assert isinstance(result["port"], str)
        assert result["enabled"] == "true"
        assert isinstance(result["enabled"], str)

        Path(f.name).unlink()


def test_hydrate_config_with_spec_invalid_values_fallback(sample_spec):
    """Test hydrate_config with spec falls back to strings for invalid values."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write("port=not_a_number\n")
        f.write("enabled=maybe\n")
        f.flush()

        config = {}
        result = hydrate_config(config, spec=sample_spec, dotenv_file_uris=f.name)

        # Invalid values should fallback to strings
        assert result["port"] == "not_a_number"
        assert isinstance(result["port"], str)
        assert result["enabled"] == "maybe"
        assert isinstance(result["enabled"], str)

        Path(f.name).unlink()


def test_hydrate_config_with_spec_preserves_existing_typed_values(sample_spec):
    """Test hydrate_config with spec preserves existing typed values in config."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write("api_key=new_key\n")
        f.write("port=9000\n")
        f.flush()

        # Config already has port as an integer
        config = {
            "host": "localhost",
            "port": 8080,
            "max_connections": 100,
        }
        result = hydrate_config(config, spec=sample_spec, dotenv_file_uris=f.name)

        # Secrets should overwrite and be cast
        assert result["api_key"] == "new_key"
        assert result["port"] == 9000
        assert isinstance(result["port"], int)
        # Existing value not overwritten
        assert result["max_connections"] == 100

        Path(f.name).unlink()


def test_hydrate_config_with_spec_nested_secrets(sample_spec):
    """Test hydrate_config with spec and nested secrets."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write("credentials.password=secret123\n")
        f.write("credentials.user_id=99\n")
        f.write("oauth.client_secret=oauth_secret\n")
        f.flush()

        config = {"host": "localhost"}
        result = hydrate_config(config, spec=sample_spec, dotenv_file_uris=f.name)

        assert result["credentials"]["password"] == "secret123"
        assert result["credentials"]["user_id"] == 99
        assert isinstance(result["credentials"]["user_id"], int)
        assert result["oauth"]["client_secret"] == "oauth_secret"

        Path(f.name).unlink()


def test_hydrate_config_with_spec_boolean_variations(sample_spec):
    """Test hydrate_config with various boolean string representations."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write("enabled=yes\n")
        f.flush()

        config = {}
        result = hydrate_config(config, spec=sample_spec, dotenv_file_uris=f.name)

        assert result["enabled"] is True
        assert isinstance(result["enabled"], bool)

        Path(f.name).unlink()

    # Test with "1"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write("enabled=1\n")
        f.flush()

        config = {}
        result = hydrate_config(config, spec=sample_spec, dotenv_file_uris=f.name)

        assert result["enabled"] is True

        Path(f.name).unlink()

    # Test with "FALSE"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write("enabled=FALSE\n")
        f.flush()

        config = {}
        result = hydrate_config(config, spec=sample_spec, dotenv_file_uris=f.name)

        assert result["enabled"] is False

        Path(f.name).unlink()


def test_hydrate_config_with_spec_array_and_object_types():
    """Test hydrate_config with array and object type fields."""
    spec = {
        "connection_specification": {
            "properties": {
                "tags": {"type": "array"},
                "metadata": {"type": "object"},
            }
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write('tags=["tag1", "tag2", "tag3"]\n')
        f.write('metadata={"key": "value", "count": 42}\n')
        f.flush()

        config = {}
        result = hydrate_config(config, spec=spec, dotenv_file_uris=f.name)

        assert result["tags"] == ["tag1", "tag2", "tag3"]
        assert isinstance(result["tags"], list)
        assert result["metadata"] == {"key": "value", "count": 42}
        assert isinstance(result["metadata"], dict)

        Path(f.name).unlink()


def test_hydrate_config_with_empty_spec():
    """Test hydrate_config with an empty spec (no type casting)."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write("port=8080\n")
        f.flush()

        config = {}
        result = hydrate_config(config, spec={}, dotenv_file_uris=f.name)

        # Empty spec means no casting
        assert result["port"] == "8080"
        assert isinstance(result["port"], str)

        Path(f.name).unlink()
