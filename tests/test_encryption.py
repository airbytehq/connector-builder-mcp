"""Tests for session-scoped encryption functionality."""

import base64
import json
import os
from unittest.mock import patch

import pytest
from nacl.public import PublicKey, SealedBox

from connector_builder_mcp._encryption import (
    EncryptedSecret,
    SessionEncryptionManager,
    SessionKeyPair,
    get_encryption_instructions,
    is_encryption_enabled,
)


class TestSessionKeyPair:
    """Tests for SessionKeyPair model."""

    def test_session_keypair_creation(self) -> None:
        """Test creating a SessionKeyPair."""
        keypair = SessionKeyPair(
            kid="test-kid-123",
            public_key_b64="dGVzdC1wdWJsaWMta2V5",
            algorithm="libsodium-sealed-box",
            encoding="base64",
        )

        assert keypair.kid == "test-kid-123"
        assert keypair.public_key_b64 == "dGVzdC1wdWJsaWMta2V5"
        assert keypair.algorithm == "libsodium-sealed-box"
        assert keypair.encoding == "base64"

    def test_session_keypair_immutable(self) -> None:
        """Test that SessionKeyPair is immutable."""
        keypair = SessionKeyPair(
            kid="test-kid",
            public_key_b64="dGVzdC1wdWJsaWMta2V5",
        )

        with pytest.raises((ValueError, AttributeError)):
            keypair.kid = "new-kid"


class TestEncryptedSecret:
    """Tests for EncryptedSecret model."""

    def test_encrypted_secret_creation(self) -> None:
        """Test creating an EncryptedSecret."""
        secret = EncryptedSecret(
            ciphertext="encrypted-data",
            kid="test-kid",
            algorithm="libsodium-sealed-box",
        )

        assert secret.ciphertext == "encrypted-data"
        assert secret.kid == "test-kid"
        assert secret.algorithm == "libsodium-sealed-box"


class TestSessionEncryptionManager:
    """Tests for SessionEncryptionManager."""

    def test_manager_initialization(self) -> None:
        """Test that manager initializes with a keypair."""
        manager = SessionEncryptionManager()

        assert manager.kid is not None
        assert len(manager.kid) > 0

        public_key_info = manager.public_key_info
        assert isinstance(public_key_info, SessionKeyPair)
        assert public_key_info.kid == manager.kid
        assert public_key_info.algorithm == "libsodium-sealed-box"
        assert public_key_info.encoding == "base64"

    def test_public_key_is_valid_base64(self) -> None:
        """Test that public key is valid base64."""
        manager = SessionEncryptionManager()
        public_key_info = manager.public_key_info

        try:
            decoded = base64.b64decode(public_key_info.public_key_b64)
            assert len(decoded) == 32
        except Exception as e:
            pytest.fail(f"Public key is not valid base64: {e}")

    def test_encrypt_decrypt_roundtrip(self) -> None:
        """Test encrypting and decrypting a secret."""
        manager = SessionEncryptionManager()
        public_key_info = manager.public_key_info

        secret_plaintext = "my-secret-api-key-12345"

        public_key_bytes = base64.b64decode(public_key_info.public_key_b64)
        public_key = PublicKey(public_key_bytes)
        sealed_box = SealedBox(public_key)

        ciphertext_bytes = sealed_box.encrypt(secret_plaintext.encode("utf-8"))
        ciphertext_b64 = base64.b64encode(ciphertext_bytes).decode("ascii")

        encrypted_secret = EncryptedSecret(
            ciphertext=ciphertext_b64,
            kid=public_key_info.kid,
            algorithm="libsodium-sealed-box",
        )

        decrypted = manager.decrypt_secret(encrypted_secret)
        assert decrypted == secret_plaintext

    def test_decrypt_with_wrong_kid(self) -> None:
        """Test that decryption fails with wrong kid."""
        manager = SessionEncryptionManager()
        public_key_info = manager.public_key_info

        secret_plaintext = "my-secret"
        public_key_bytes = base64.b64decode(public_key_info.public_key_b64)
        public_key = PublicKey(public_key_bytes)
        sealed_box = SealedBox(public_key)

        ciphertext_bytes = sealed_box.encrypt(secret_plaintext.encode("utf-8"))
        ciphertext_b64 = base64.b64encode(ciphertext_bytes).decode("ascii")

        encrypted_secret = EncryptedSecret(
            ciphertext=ciphertext_b64,
            kid="wrong-kid",
            algorithm="libsodium-sealed-box",
        )

        with pytest.raises(ValueError, match="Key ID mismatch"):
            manager.decrypt_secret(encrypted_secret)

    def test_decrypt_with_wrong_algorithm(self) -> None:
        """Test that decryption fails with unsupported algorithm."""
        manager = SessionEncryptionManager()

        encrypted_secret = EncryptedSecret(
            ciphertext="some-ciphertext",
            kid=manager.kid,
            algorithm="unsupported-algorithm",
        )

        with pytest.raises(ValueError, match="Unsupported algorithm"):
            manager.decrypt_secret(encrypted_secret)

    def test_decrypt_with_invalid_base64(self) -> None:
        """Test that decryption fails with invalid base64."""
        manager = SessionEncryptionManager()

        encrypted_secret = EncryptedSecret(
            ciphertext="not-valid-base64!!!",
            kid=manager.kid,
            algorithm="libsodium-sealed-box",
        )

        with pytest.raises(ValueError, match="Invalid base64 ciphertext"):
            manager.decrypt_secret(encrypted_secret)

    def test_decrypt_with_invalid_ciphertext(self) -> None:
        """Test that decryption fails with invalid ciphertext."""
        manager = SessionEncryptionManager()

        invalid_ciphertext = base64.b64encode(b"invalid-ciphertext-data").decode("ascii")

        encrypted_secret = EncryptedSecret(
            ciphertext=invalid_ciphertext,
            kid=manager.kid,
            algorithm="libsodium-sealed-box",
        )

        with pytest.raises(ValueError, match="Decryption failed"):
            manager.decrypt_secret(encrypted_secret)

    def test_decrypt_with_oversized_ciphertext(self) -> None:
        """Test that decryption fails with oversized ciphertext."""
        manager = SessionEncryptionManager()

        oversized_data = b"x" * (64 * 1024 + 1)
        oversized_ciphertext = base64.b64encode(oversized_data).decode("ascii")

        encrypted_secret = EncryptedSecret(
            ciphertext=oversized_ciphertext,
            kid=manager.kid,
            algorithm="libsodium-sealed-box",
        )

        with pytest.raises(ValueError, match="Ciphertext too large"):
            manager.decrypt_secret(encrypted_secret)

    def test_multiple_managers_have_different_keys(self) -> None:
        """Test that different managers have different keys."""
        manager1 = SessionEncryptionManager()
        manager2 = SessionEncryptionManager()

        assert manager1.kid != manager2.kid
        assert manager1.public_key_info.public_key_b64 != manager2.public_key_info.public_key_b64

    def test_decrypt_json_config(self) -> None:
        """Test decrypting a JSON configuration."""
        manager = SessionEncryptionManager()
        public_key_info = manager.public_key_info

        config = {"api_key": "secret-key-123", "base_url": "https://api.example.com"}
        config_json = json.dumps(config)

        public_key_bytes = base64.b64decode(public_key_info.public_key_b64)
        public_key = PublicKey(public_key_bytes)
        sealed_box = SealedBox(public_key)

        ciphertext_bytes = sealed_box.encrypt(config_json.encode("utf-8"))
        ciphertext_b64 = base64.b64encode(ciphertext_bytes).decode("ascii")

        encrypted_secret = EncryptedSecret(
            ciphertext=ciphertext_b64,
            kid=public_key_info.kid,
            algorithm="libsodium-sealed-box",
        )

        decrypted_json = manager.decrypt_secret(encrypted_secret)
        decrypted_config = json.loads(decrypted_json)

        assert decrypted_config == config


class TestEncryptionFeatureFlag:
    """Tests for encryption feature flag."""

    def test_is_encryption_enabled_false_by_default(self) -> None:
        """Test that encryption is disabled by default."""
        with patch.dict(os.environ, {}, clear=True):
            assert is_encryption_enabled() is False

    def test_is_encryption_enabled_with_true(self) -> None:
        """Test that encryption is enabled with 'true'."""
        with patch.dict(os.environ, {"CONNECTOR_BUILDER_MCP_ENABLE_ENCRYPTION": "true"}):
            assert is_encryption_enabled() is True

    def test_is_encryption_enabled_with_1(self) -> None:
        """Test that encryption is enabled with '1'."""
        with patch.dict(os.environ, {"CONNECTOR_BUILDER_MCP_ENABLE_ENCRYPTION": "1"}):
            assert is_encryption_enabled() is True

    def test_is_encryption_enabled_with_yes(self) -> None:
        """Test that encryption is enabled with 'yes'."""
        with patch.dict(os.environ, {"CONNECTOR_BUILDER_MCP_ENABLE_ENCRYPTION": "yes"}):
            assert is_encryption_enabled() is True

    def test_is_encryption_enabled_case_insensitive(self) -> None:
        """Test that encryption flag is case insensitive."""
        with patch.dict(os.environ, {"CONNECTOR_BUILDER_MCP_ENABLE_ENCRYPTION": "TRUE"}):
            assert is_encryption_enabled() is True

        with patch.dict(os.environ, {"CONNECTOR_BUILDER_MCP_ENABLE_ENCRYPTION": "Yes"}):
            assert is_encryption_enabled() is True

    def test_is_encryption_enabled_with_false(self) -> None:
        """Test that encryption is disabled with 'false'."""
        with patch.dict(os.environ, {"CONNECTOR_BUILDER_MCP_ENABLE_ENCRYPTION": "false"}):
            assert is_encryption_enabled() is False


class TestEncryptionInstructions:
    """Tests for encryption instructions."""

    def test_get_encryption_instructions_returns_string(self) -> None:
        """Test that get_encryption_instructions returns a string."""
        instructions = get_encryption_instructions()
        assert isinstance(instructions, str)
        assert len(instructions) > 0

    def test_instructions_contain_key_information(self) -> None:
        """Test that instructions contain key information."""
        instructions = get_encryption_instructions()

        assert "public key" in instructions.lower()
        assert "encrypt" in instructions.lower()
        assert "ciphertext" in instructions.lower()
        assert "libsodium" in instructions.lower()
        assert "sealed-box" in instructions.lower()
