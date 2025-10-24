"""Tests for session-scoped encryption functionality."""

import base64
import json
import os
from unittest.mock import patch

import pytest

from connector_builder_mcp.encryption import (
    MAX_CIPHERTEXT_SIZE,
    EncryptedSecret,
    destroy_session_keypair,
)


@pytest.fixture(autouse=True)
def cleanup_session_keypair():
    """Cleanup session keypair before and after each test."""
    destroy_session_keypair()
    yield
    destroy_session_keypair()


def test_is_encryption_enabled_default():
    """Test that encryption is disabled by default."""
    with patch.dict(os.environ, {}, clear=True):
        # Re-import to pick up env var changes
        from importlib import reload

        from connector_builder_mcp import encryption

        reload(encryption)
        assert not encryption.is_encryption_enabled()


def test_is_encryption_enabled_various_values():
    """Test encryption enabled with various env var values."""
    for value in ["1", "true", "True", "TRUE", "yes", "Yes", "YES", "on", "On", "ON"]:
        with patch.dict(os.environ, {"ENABLE_SESSION_ENCRYPTION": value}, clear=True):
            from importlib import reload

            from connector_builder_mcp import encryption

            reload(encryption)
            assert encryption.is_encryption_enabled(), f"Failed for value: {value}"


def test_is_encryption_enabled_false_values():
    """Test encryption disabled with various env var values."""
    for value in ["0", "false", "False", "no", "off", "", "anything"]:
        with patch.dict(os.environ, {"ENABLE_SESSION_ENCRYPTION": value}, clear=True):
            from importlib import reload

            from connector_builder_mcp import encryption

            reload(encryption)
            assert not encryption.is_encryption_enabled(), f"Failed for value: {value}"


@patch.dict(os.environ, {"ENABLE_SESSION_ENCRYPTION": "true"}, clear=True)
def test_initialize_session_keypair():
    """Test session keypair initialization."""
    from importlib import reload

    from connector_builder_mcp import encryption

    reload(encryption)

    encryption.initialize_session_keypair()

    # Check that keypair was initialized
    public_key_info = encryption.get_public_key_info()
    assert public_key_info is not None
    assert public_key_info.kid != ""
    assert public_key_info.alg == "libsodium-sealedbox"
    assert public_key_info.encoding == "base64"
    assert public_key_info.max_size_bytes == MAX_CIPHERTEXT_SIZE
    assert len(public_key_info.public_key) > 0

    # Verify public key is valid base64
    public_key_bytes = base64.b64decode(public_key_info.public_key)
    assert len(public_key_bytes) == 32  # X25519 public key size


@patch.dict(os.environ, {"ENABLE_SESSION_ENCRYPTION": "true"}, clear=True)
def test_destroy_session_keypair():
    """Test session keypair destruction."""
    from importlib import reload

    from connector_builder_mcp import encryption

    reload(encryption)

    encryption.initialize_session_keypair()
    assert encryption.get_public_key_info() is not None

    encryption.destroy_session_keypair()
    assert encryption.get_public_key_info() is None


@patch.dict(os.environ, {"ENABLE_SESSION_ENCRYPTION": "true"}, clear=True)
def test_encrypt_decrypt_roundtrip():
    """Test encryption and decryption roundtrip."""
    from importlib import reload

    from connector_builder_mcp import encryption

    reload(encryption)

    encryption.initialize_session_keypair()

    # Test plaintext
    plaintext = "my-secret-api-key"

    # Encrypt
    encrypted = encryption.encrypt_for_testing(plaintext)
    assert encrypted.ciphertext != ""
    assert encrypted.kid != ""

    # Decrypt
    decrypted = encryption.decrypt_secret(encrypted)
    assert decrypted == plaintext


@patch.dict(os.environ, {"ENABLE_SESSION_ENCRYPTION": "true"}, clear=True)
def test_decrypt_with_dict_input():
    """Test decryption with dict input."""
    from importlib import reload

    from connector_builder_mcp import encryption

    reload(encryption)

    encryption.initialize_session_keypair()

    plaintext = "test-secret"
    encrypted = encryption.encrypt_for_testing(plaintext)

    # Decrypt with dict
    encrypted_dict = {"ciphertext": encrypted.ciphertext, "kid": encrypted.kid}
    decrypted = encryption.decrypt_secret(encrypted_dict)
    assert decrypted == plaintext


@patch.dict(os.environ, {"ENABLE_SESSION_ENCRYPTION": "true"}, clear=True)
def test_decrypt_kid_mismatch():
    """Test decryption fails with kid mismatch."""
    from importlib import reload

    from connector_builder_mcp import encryption

    reload(encryption)

    encryption.initialize_session_keypair()

    plaintext = "test-secret"
    encrypted = encryption.encrypt_for_testing(plaintext)

    # Change kid
    encrypted.kid = "wrong-kid"

    # Decrypt should fail
    with pytest.raises(ValueError, match="Key ID mismatch"):
        encryption.decrypt_secret(encrypted)


@patch.dict(os.environ, {"ENABLE_SESSION_ENCRYPTION": "true"}, clear=True)
def test_decrypt_invalid_base64():
    """Test decryption fails with invalid base64 ciphertext."""
    from importlib import reload

    from connector_builder_mcp import encryption

    reload(encryption)

    encryption.initialize_session_keypair()

    public_key_info = encryption.get_public_key_info()
    assert public_key_info is not None

    # Invalid base64
    encrypted = EncryptedSecret(ciphertext="not-valid-base64!!!", kid=public_key_info.kid)

    with pytest.raises(ValueError, match="Invalid base64 ciphertext"):
        encryption.decrypt_secret(encrypted)


@patch.dict(os.environ, {"ENABLE_SESSION_ENCRYPTION": "true"}, clear=True)
def test_decrypt_invalid_ciphertext():
    """Test decryption fails with invalid ciphertext."""
    from importlib import reload

    from connector_builder_mcp import encryption

    reload(encryption)

    encryption.initialize_session_keypair()

    public_key_info = encryption.get_public_key_info()
    assert public_key_info is not None

    # Valid base64 but invalid ciphertext
    encrypted = EncryptedSecret(
        ciphertext=base64.b64encode(b"invalid-ciphertext").decode("ascii"),
        kid=public_key_info.kid,
    )

    with pytest.raises(ValueError, match="Decryption failed"):
        encryption.decrypt_secret(encrypted)


@patch.dict(os.environ, {"ENABLE_SESSION_ENCRYPTION": "true"}, clear=True)
def test_decrypt_ciphertext_too_large():
    """Test decryption fails with ciphertext exceeding size limit."""
    from importlib import reload

    from connector_builder_mcp import encryption

    reload(encryption)

    encryption.initialize_session_keypair()

    public_key_info = encryption.get_public_key_info()
    assert public_key_info is not None

    # Create oversized ciphertext (just over 64 KB)
    large_data = b"x" * (MAX_CIPHERTEXT_SIZE + 1)
    encrypted = EncryptedSecret(
        ciphertext=base64.b64encode(large_data).decode("ascii"),
        kid=public_key_info.kid,
    )

    with pytest.raises(ValueError, match="Ciphertext too large"):
        encryption.decrypt_secret(encrypted)


@patch.dict(os.environ, {"ENABLE_SESSION_ENCRYPTION": "true"}, clear=True)
def test_get_public_key_resource():
    """Test getting public key resource as JSON."""
    from importlib import reload

    from connector_builder_mcp import encryption

    reload(encryption)

    encryption.initialize_session_keypair()

    resource_json = encryption.get_public_key_resource()
    resource_data = json.loads(resource_json)

    assert "kid" in resource_data
    assert "alg" in resource_data
    assert "public_key" in resource_data
    assert "encoding" in resource_data
    assert "max_size_bytes" in resource_data

    assert resource_data["alg"] == "libsodium-sealedbox"
    assert resource_data["encoding"] == "base64"
    assert resource_data["max_size_bytes"] == MAX_CIPHERTEXT_SIZE


def test_get_public_key_resource_disabled():
    """Test getting public key resource when encryption is disabled."""
    with patch.dict(os.environ, {}, clear=True):
        from importlib import reload

        from connector_builder_mcp import encryption

        reload(encryption)

        resource_json = encryption.get_public_key_resource()
        resource_data = json.loads(resource_json)

        assert "error" in resource_data
        assert "encryption is not enabled" in resource_data["error"].lower()


@patch.dict(os.environ, {"ENABLE_SESSION_ENCRYPTION": "true"}, clear=True)
def test_get_public_key_resource_not_initialized():
    """Test getting public key resource when keypair not initialized."""
    from importlib import reload

    from connector_builder_mcp import encryption

    reload(encryption)

    # Don't initialize keypair
    resource_json = encryption.get_public_key_resource()
    resource_data = json.loads(resource_json)

    assert "error" in resource_data
    assert "not initialized" in resource_data["error"].lower()


def test_decrypt_secret_disabled():
    """Test decryption fails when encryption is disabled."""
    with patch.dict(os.environ, {}, clear=True):
        from importlib import reload

        from connector_builder_mcp import encryption

        reload(encryption)

        encrypted = EncryptedSecret(ciphertext="test", kid="test-kid")

        with pytest.raises(ValueError, match="encryption is not enabled"):
            encryption.decrypt_secret(encrypted)


@patch.dict(os.environ, {"ENABLE_SESSION_ENCRYPTION": "true"}, clear=True)
def test_decrypt_secret_not_initialized():
    """Test decryption fails when keypair not initialized."""
    from importlib import reload

    from connector_builder_mcp import encryption

    reload(encryption)

    # Don't initialize keypair
    encrypted = EncryptedSecret(ciphertext="test", kid="test-kid")

    with pytest.raises(ValueError, match="not initialized"):
        encryption.decrypt_secret(encrypted)


@patch.dict(os.environ, {"ENABLE_SESSION_ENCRYPTION": "true"}, clear=True)
def test_encrypt_for_testing_disabled():
    """Test encrypt_for_testing fails when encryption is disabled."""
    with patch.dict(os.environ, {}, clear=True):
        from importlib import reload

        from connector_builder_mcp import encryption

        reload(encryption)

        with pytest.raises(ValueError, match="encryption is not enabled"):
            encryption.encrypt_for_testing("test")


@patch.dict(os.environ, {"ENABLE_SESSION_ENCRYPTION": "true"}, clear=True)
def test_encrypt_for_testing_not_initialized():
    """Test encrypt_for_testing fails when keypair not initialized."""
    from importlib import reload

    from connector_builder_mcp import encryption

    reload(encryption)

    # Don't initialize keypair
    with pytest.raises(ValueError, match="not initialized"):
        encryption.encrypt_for_testing("test")


@patch.dict(os.environ, {"ENABLE_SESSION_ENCRYPTION": "true"}, clear=True)
def test_multiple_secrets_encryption():
    """Test encrypting and decrypting multiple different secrets."""
    from importlib import reload

    from connector_builder_mcp import encryption

    reload(encryption)

    encryption.initialize_session_keypair()

    secrets = [
        "api-key-12345",
        "password!@#$%",
        "very-long-secret-" + "x" * 1000,
        "unicode-secret-🔐",
    ]

    for secret in secrets:
        encrypted = encryption.encrypt_for_testing(secret)
        decrypted = encryption.decrypt_secret(encrypted)
        assert decrypted == secret


@patch.dict(os.environ, {"ENABLE_SESSION_ENCRYPTION": "true"}, clear=True)
def test_ciphertext_size_under_limit():
    """Test that ciphertext under size limit is accepted."""
    from importlib import reload

    from connector_builder_mcp import encryption

    reload(encryption)

    encryption.initialize_session_keypair()

    # Create a secret that will result in ciphertext under the limit
    # Sealed box adds 48 bytes overhead
    max_plaintext_size = MAX_CIPHERTEXT_SIZE - 48 - 100  # Extra margin for safety
    large_secret = "x" * max_plaintext_size

    encrypted = encryption.encrypt_for_testing(large_secret)
    decrypted = encryption.decrypt_secret(encrypted)
    assert decrypted == large_secret


@patch.dict(os.environ, {"ENABLE_SESSION_ENCRYPTION": "true"}, clear=True)
def test_public_key_info_structure():
    """Test PublicKeyInfo structure and validation."""
    from importlib import reload

    from connector_builder_mcp import encryption

    reload(encryption)

    encryption.initialize_session_keypair()

    public_key_info = encryption.get_public_key_info()
    assert public_key_info is not None

    # Validate PublicKeyInfo fields
    assert hasattr(public_key_info, "kid")
    assert hasattr(public_key_info, "alg")
    assert hasattr(public_key_info, "public_key")
    assert hasattr(public_key_info, "encoding")
    assert hasattr(public_key_info, "max_size_bytes")

    assert isinstance(public_key_info.kid, str)
    assert isinstance(public_key_info.alg, str)
    assert isinstance(public_key_info.public_key, str)
    assert isinstance(public_key_info.encoding, str)
    assert isinstance(public_key_info.max_size_bytes, int)

    # Validate values
    assert public_key_info.alg == "libsodium-sealedbox"
    assert public_key_info.encoding == "base64"
    assert public_key_info.max_size_bytes == MAX_CIPHERTEXT_SIZE

    # Validate public key can be decoded
    public_key_bytes = base64.b64decode(public_key_info.public_key)
    assert len(public_key_bytes) == 32


@patch.dict(os.environ, {"ENABLE_SESSION_ENCRYPTION": "true"}, clear=True)
def test_encrypted_secret_structure():
    """Test EncryptedSecret structure and validation."""
    from importlib import reload

    from connector_builder_mcp import encryption

    reload(encryption)

    encryption.initialize_session_keypair()

    plaintext = "test-secret"
    encrypted = encryption.encrypt_for_testing(plaintext)

    # Validate EncryptedSecret fields
    assert hasattr(encrypted, "ciphertext")
    assert hasattr(encrypted, "kid")

    assert isinstance(encrypted.ciphertext, str)
    assert isinstance(encrypted.kid, str)

    # Validate ciphertext is valid base64
    ciphertext_bytes = base64.b64decode(encrypted.ciphertext)
    assert len(ciphertext_bytes) > 0

    # Validate kid matches session
    public_key_info = encryption.get_public_key_info()
    assert public_key_info is not None
    assert encrypted.kid == public_key_info.kid
