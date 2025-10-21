"""Tests for secrets management functionality."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from connector_builder_mcp.secrets import (
    SecretsFileInfo,
    _load_secrets,
    get_encryption_instructions,
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

    with patch("connector_builder_mcp.secrets._load_secrets", return_value={}):
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


@patch.dict(os.environ, {"ENABLE_SESSION_ENCRYPTION": "true"}, clear=True)
def test_hydrate_config_with_encrypted_secrets():
    """Test hydration with encrypted secrets."""
    from importlib import reload

    from connector_builder_mcp import encryption

    reload(encryption)
    encryption.initialize_session_keypair()

    # Create encrypted secrets
    api_key_plaintext = "secret-api-key-12345"
    password_plaintext = "secret-password-67890"

    encrypted_api_key = encryption.encrypt_for_testing(api_key_plaintext)
    encrypted_password = encryption.encrypt_for_testing(password_plaintext)

    config = {"host": "localhost", "credentials": {"username": "user"}}

    encrypted_secrets = {
        "api_key": {
            "ciphertext": encrypted_api_key.ciphertext,
            "kid": encrypted_api_key.kid,
        },
        "credentials.password": {
            "ciphertext": encrypted_password.ciphertext,
            "kid": encrypted_password.kid,
        },
    }

    result = hydrate_config(config, encrypted_secrets=encrypted_secrets)

    expected = {
        "host": "localhost",
        "api_key": api_key_plaintext,
        "credentials": {"username": "user", "password": password_plaintext},
    }
    assert result == expected

    encryption.destroy_session_keypair()


def test_hydrate_config_with_encrypted_secrets_disabled():
    """Test hydration with encrypted secrets when encryption is disabled."""
    with patch.dict(os.environ, {}, clear=True):
        from importlib import reload

        from connector_builder_mcp import encryption

        reload(encryption)

        config = {"host": "localhost"}
        encrypted_secrets = {
            "api_key": {"ciphertext": "test", "kid": "test-kid"}
        }

        with pytest.raises(ValueError, match="session encryption is not enabled"):
            hydrate_config(config, encrypted_secrets=encrypted_secrets)


@patch.dict(os.environ, {"ENABLE_SESSION_ENCRYPTION": "true"}, clear=True)
def test_hydrate_config_with_both_dotenv_and_encrypted():
    """Test hydration with both dotenv files and encrypted secrets."""
    from importlib import reload

    from connector_builder_mcp import encryption

    reload(encryption)
    encryption.initialize_session_keypair()

    # Create a dotenv file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write("host=example.com\n")
        f.write("port=8080\n")
        f.flush()
        dotenv_file = f.name

    # Create encrypted secret
    api_key_plaintext = "encrypted-api-key"
    encrypted_api_key = encryption.encrypt_for_testing(api_key_plaintext)

    config = {"existing_key": "existing_value"}

    encrypted_secrets = {
        "api_key": {
            "ciphertext": encrypted_api_key.ciphertext,
            "kid": encrypted_api_key.kid,
        }
    }

    result = hydrate_config(
        config, dotenv_file_uris=dotenv_file, encrypted_secrets=encrypted_secrets
    )

    expected = {
        "existing_key": "existing_value",
        "host": "example.com",
        "port": "8080",
        "api_key": api_key_plaintext,
    }
    assert result == expected

    Path(dotenv_file).unlink()
    encryption.destroy_session_keypair()


@patch.dict(os.environ, {"ENABLE_SESSION_ENCRYPTION": "true"}, clear=True)
def test_hydrate_config_encrypted_secret_decryption_failure():
    """Test hydration fails gracefully when encrypted secret decryption fails."""
    from importlib import reload

    from connector_builder_mcp import encryption

    reload(encryption)
    encryption.initialize_session_keypair()

    config = {"host": "localhost"}

    # Invalid encrypted secret
    encrypted_secrets = {
        "api_key": {"ciphertext": "invalid-base64!!!", "kid": "wrong-kid"}
    }

    with pytest.raises(ValueError, match="Failed to decrypt secret"):
        hydrate_config(config, encrypted_secrets=encrypted_secrets)

    encryption.destroy_session_keypair()


def test_get_encryption_instructions_disabled():
    """Test getting encryption instructions when encryption is disabled."""
    # Note: We can't reliably test this with module reload because the ENABLE_SESSION_ENCRYPTION
    # flag is set at import time. Instead, we test the behavior through the actual functions.
    with patch("connector_builder_mcp.encryption.is_encryption_enabled", return_value=False):
        instructions = get_encryption_instructions()
        assert "not enabled" in instructions.lower()
        assert "ENABLE_SESSION_ENCRYPTION" in instructions


@patch.dict(os.environ, {"ENABLE_SESSION_ENCRYPTION": "true"}, clear=True)
def test_get_encryption_instructions_enabled():
    """Test getting encryption instructions when encryption is enabled."""
    from importlib import reload

    from connector_builder_mcp import encryption

    reload(encryption)
    encryption.initialize_session_keypair()

    instructions = get_encryption_instructions()
    assert "enabled" in instructions.lower()
    assert "public key" in instructions.lower()
    assert "ciphertext" in instructions.lower()
    assert "kid" in instructions.lower()

    # Check that the actual public key info is included
    public_key_info = encryption.get_public_key_info()
    assert public_key_info is not None
    assert public_key_info.kid in instructions
    assert public_key_info.public_key in instructions

    encryption.destroy_session_keypair()


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


@patch("connector_builder_mcp.secrets.privatebin.get")
@patch("connector_builder_mcp.secrets.os.getenv")
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


@patch("connector_builder_mcp.secrets.os.getenv")
def test_load_secrets_privatebin_url_no_password(mock_getenv):
    """Test loading from privatebin URL without PRIVATEBIN_PASSWORD fails."""
    mock_getenv.return_value = None

    secrets = _load_secrets("https://privatebin.net/?abc123#test_passphrase")

    assert secrets == {}
    mock_getenv.assert_called_with("PRIVATEBIN_PASSWORD")


@patch("connector_builder_mcp.secrets.os.getenv")
@patch("connector_builder_mcp.secrets.requests.get")
def test_load_secrets_privatebin_url_with_existing_password_param(mock_get, mock_getenv):
    """Test loading from privatebin URL with embedded password fails validation."""
    mock_getenv.return_value = "test_password"
    mock_response = mock_get.return_value
    mock_response.text = "api_key=secret123\n"
    mock_response.raise_for_status.return_value = None

    secrets = _load_secrets("https://privatebin.net/abc123?password=existing_pass")

    assert secrets == {}


@patch("connector_builder_mcp.secrets.privatebin.get")
@patch("connector_builder_mcp.secrets.os.getenv")
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


@patch("connector_builder_mcp.secrets.os.getenv")
@patch("connector_builder_mcp.secrets._fetch_privatebin_content")
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


@patch("connector_builder_mcp.secrets.os.getenv")
def test_populate_dotenv_missing_secrets_stubs_privatebin_url(mock_getenv):
    """Test populate stubs with privatebin URL returns instructions."""
    mock_getenv.return_value = "test_password"
    with patch("connector_builder_mcp.secrets._load_secrets") as mock_load:
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


@patch("connector_builder_mcp.secrets.os.getenv")
def test_populate_dotenv_missing_secrets_stubs_privatebin_all_present(mock_getenv):
    """Test populate stubs with privatebin URL when all secrets are present."""
    mock_getenv.return_value = "test_password"
    with patch("connector_builder_mcp.secrets._load_secrets") as mock_load:
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
    from connector_builder_mcp.secrets import _validate_secrets_uris

    with tempfile.NamedTemporaryFile(suffix=".env", delete=False) as f:
        absolute_path = str(Path(f.name).resolve())
        errors = _validate_secrets_uris(absolute_path)
        assert errors == []
        Path(f.name).unlink()


def test_validate_secrets_uris_relative_path_invalid():
    """Test validation fails for relative paths."""
    from connector_builder_mcp.secrets import _validate_secrets_uris

    errors = _validate_secrets_uris("relative/path/.env")
    assert len(errors) == 1
    assert "must be absolute" in errors[0]
    assert "relative/path/.env" in errors[0]


@patch("connector_builder_mcp.secrets.os.getenv")
def test_validate_secrets_uris_privatebin_no_password(mock_getenv):
    """Test validation fails for privatebin URL without PRIVATEBIN_PASSWORD."""
    from connector_builder_mcp.secrets import _validate_secrets_uris

    mock_getenv.return_value = None
    errors = _validate_secrets_uris("https://privatebin.net/abc123")
    assert len(errors) == 1
    assert "requires PRIVATEBIN_PASSWORD environment variable" in errors[0]


@patch("connector_builder_mcp.secrets.os.getenv")
def test_validate_secrets_uris_privatebin_with_password_valid(mock_getenv):
    """Test validation passes for privatebin URL with PRIVATEBIN_PASSWORD set."""
    from connector_builder_mcp.secrets import _validate_secrets_uris

    mock_getenv.return_value = "test_password"
    errors = _validate_secrets_uris("https://privatebin.net/abc123")
    assert errors == []


@patch("connector_builder_mcp.secrets.os.getenv")
def test_validate_secrets_uris_privatebin_embedded_password_invalid(mock_getenv):
    """Test validation fails for privatebin URL with embedded password."""
    from connector_builder_mcp.secrets import _validate_secrets_uris

    mock_getenv.return_value = "test_password"
    errors = _validate_secrets_uris("https://privatebin.net/abc123?password=embedded")
    assert len(errors) == 1
    assert "contains embedded password" in errors[0]
    assert "not allowed for security reasons" in errors[0]


@patch("connector_builder_mcp.secrets.os.getenv")
def test_validate_secrets_uris_mixed_valid_invalid(mock_getenv):
    """Test validation with mix of valid and invalid URIs."""
    from connector_builder_mcp.secrets import _validate_secrets_uris

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
