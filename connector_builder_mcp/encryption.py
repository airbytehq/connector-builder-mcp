# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Session-scoped encryption for remote secrets.

This module provides per-session keypair generation and encryption/decryption
for secrets without exposing plaintext to the LLM or persisting plaintext on the server.

Uses libsodium sealed-box (X25519 + XSalsa20-Poly1305) for simplicity and
copy-paste friendliness in the MVP phase.
"""

import base64
import json
import logging
import os
from typing import Any

import nacl.public
import nacl.utils
from pydantic import BaseModel, Field


logger = logging.getLogger(__name__)

# Feature flag - off by default
ENABLE_SESSION_ENCRYPTION = os.getenv("ENABLE_SESSION_ENCRYPTION", "").lower() in (
    "1",
    "true",
    "yes",
    "on",
)

# Maximum ciphertext size (64 KB)
MAX_CIPHERTEXT_SIZE = 64 * 1024  # 64 KB

# In-memory storage for the session keypair
_session_private_key: nacl.public.PrivateKey | None = None
_session_public_key: nacl.public.PublicKey | None = None
_session_kid: str | None = None


class PublicKeyInfo(BaseModel):
    """Public key information for client-side encryption."""

    kid: str = Field(description="Key ID for this session")
    alg: str = Field(description="Algorithm: libsodium-sealedbox")
    public_key: str = Field(description="Base64-encoded public key")
    encoding: str = Field(description="Encoding format: base64")
    max_size_bytes: int = Field(description="Maximum ciphertext size in bytes")


class EncryptedSecret(BaseModel):
    """Encrypted secret input format."""

    ciphertext: str = Field(description="Base64-encoded encrypted data")
    kid: str = Field(description="Key ID matching the session public key")


def is_encryption_enabled() -> bool:
    """Check if session encryption feature is enabled.

    Returns:
        True if ENABLE_SESSION_ENCRYPTION is set, False otherwise
    """
    return ENABLE_SESSION_ENCRYPTION


def initialize_session_keypair() -> None:
    """Initialize a new session keypair.

    This should be called on server startup or session initialization.
    The private key is stored in memory only and will be destroyed on session end.
    """
    global _session_private_key, _session_public_key, _session_kid

    if not is_encryption_enabled():
        logger.info("Session encryption is disabled (ENABLE_SESSION_ENCRYPTION not set)")
        return

    # Generate new keypair
    _session_private_key = nacl.public.PrivateKey.generate()
    _session_public_key = _session_private_key.public_key

    # Generate a simple kid based on the first 8 bytes of the public key
    kid_bytes = bytes(_session_public_key)[:8]
    _session_kid = base64.urlsafe_b64encode(kid_bytes).decode("ascii").rstrip("=")

    logger.info(f"Session keypair initialized with kid: {_session_kid}")


def destroy_session_keypair() -> None:
    """Destroy the session keypair and zeroize buffers.

    This should be called on session end or timeout.
    """
    global _session_private_key, _session_public_key, _session_kid

    if _session_private_key is not None:
        # Zeroize the private key bytes if possible
        try:
            # PyNaCl doesn't expose direct buffer access, but we can at least clear the reference
            _session_private_key = None
        except Exception as e:
            logger.warning(f"Error destroying private key: {e}")

    _session_public_key = None
    _session_kid = None
    logger.info("Session keypair destroyed")


def get_public_key_info() -> PublicKeyInfo | None:
    """Get the public key information for this session.

    Returns:
        PublicKeyInfo object if encryption is enabled and keypair initialized, None otherwise
    """
    if not is_encryption_enabled():
        return None

    if _session_public_key is None or _session_kid is None:
        logger.warning("Session keypair not initialized")
        return None

    public_key_bytes = bytes(_session_public_key)
    public_key_b64 = base64.b64encode(public_key_bytes).decode("ascii")

    return PublicKeyInfo(
        kid=_session_kid,
        alg="libsodium-sealedbox",
        public_key=public_key_b64,
        encoding="base64",
        max_size_bytes=MAX_CIPHERTEXT_SIZE,
    )


def decrypt_secret(encrypted_secret: EncryptedSecret | dict[str, Any]) -> str:
    """Decrypt an encrypted secret using the session private key.

    Args:
        encrypted_secret: EncryptedSecret object or dict with ciphertext and kid

    Returns:
        Decrypted plaintext secret

    Raises:
        ValueError: If encryption is not enabled, keypair not initialized,
                    kid mismatch, invalid ciphertext, or decryption fails
    """
    if not is_encryption_enabled():
        raise ValueError("Session encryption is not enabled")

    if _session_private_key is None or _session_kid is None:
        raise ValueError("Session keypair not initialized")

    # Convert dict to EncryptedSecret if needed
    if isinstance(encrypted_secret, dict):
        encrypted_secret = EncryptedSecret(**encrypted_secret)

    # Validate kid
    if encrypted_secret.kid != _session_kid:
        raise ValueError(
            f"Key ID mismatch: expected {_session_kid}, got {encrypted_secret.kid}"
        )

    # Decode ciphertext
    try:
        ciphertext = base64.b64decode(encrypted_secret.ciphertext)
    except Exception as e:
        raise ValueError(f"Invalid base64 ciphertext: {e}") from e

    # Validate size
    if len(ciphertext) > MAX_CIPHERTEXT_SIZE:
        raise ValueError(
            f"Ciphertext too large: {len(ciphertext)} bytes (max {MAX_CIPHERTEXT_SIZE})"
        )

    # Decrypt using sealed box
    try:
        sealed_box = nacl.public.SealedBox(_session_private_key)
        plaintext_bytes = sealed_box.decrypt(ciphertext)
        plaintext = plaintext_bytes.decode("utf-8")

        # Zeroize the plaintext bytes
        try:
            # PyNaCl returns bytes, which are immutable in Python, but we can at least clear the reference
            del plaintext_bytes
        except Exception:
            pass

        return plaintext

    except Exception as e:
        raise ValueError(f"Decryption failed: {e}") from e


def get_public_key_resource() -> str:
    """Get the public key as a JSON resource for MCP clients.

    Returns:
        JSON string with public key information, or error message if not available
    """
    if not is_encryption_enabled():
        return json.dumps(
            {
                "error": "Session encryption is not enabled",
                "help": "Set ENABLE_SESSION_ENCRYPTION=true to enable this feature",
            },
            indent=2,
        )

    public_key_info = get_public_key_info()
    if public_key_info is None:
        return json.dumps(
            {
                "error": "Session keypair not initialized",
                "help": "The server should initialize the keypair on startup",
            },
            indent=2,
        )

    return json.dumps(public_key_info.model_dump(), indent=2)


def encrypt_for_testing(plaintext: str) -> EncryptedSecret:
    """Encrypt a plaintext secret for testing purposes.

    This function is primarily for testing and should not be used in production
    as it defeats the purpose of client-side encryption.

    Args:
        plaintext: Plaintext secret to encrypt

    Returns:
        EncryptedSecret object

    Raises:
        ValueError: If encryption is not enabled or keypair not initialized
    """
    if not is_encryption_enabled():
        raise ValueError("Session encryption is not enabled")

    if _session_public_key is None or _session_kid is None:
        raise ValueError("Session keypair not initialized")

    # Encrypt using sealed box
    sealed_box = nacl.public.SealedBox(_session_public_key)
    plaintext_bytes = plaintext.encode("utf-8")
    ciphertext = sealed_box.encrypt(plaintext_bytes)

    # Encode as base64
    ciphertext_b64 = base64.b64encode(ciphertext).decode("ascii")

    return EncryptedSecret(ciphertext=ciphertext_b64, kid=_session_kid)
