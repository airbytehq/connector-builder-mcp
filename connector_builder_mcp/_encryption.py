"""Session-scoped encryption for remote secrets.

This module provides per-session public/private key encryption for handling
remote secrets without exposing plaintext to the LLM or persisting plaintext
on the server.

Uses libsodium sealed-box (X25519 + XSalsa20-Poly1305) for encryption.
"""

import base64
import logging
import os
import secrets

from nacl.public import PrivateKey, SealedBox
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

MAX_CIPHERTEXT_SIZE = 64 * 1024


class SessionKeyPair(BaseModel):
    """Session keypair for encryption/decryption."""

    kid: str = Field(description="Key ID for this session")
    public_key_b64: str = Field(description="Base64-encoded public key")
    algorithm: str = Field(default="libsodium-sealed-box", description="Encryption algorithm")
    encoding: str = Field(default="base64", description="Encoding format for ciphertext")

    class Config:
        """Pydantic config."""

        frozen = True


class EncryptedSecret(BaseModel):
    """Encrypted secret payload."""

    ciphertext: str = Field(description="Base64-encoded ciphertext")
    kid: str = Field(description="Key ID used for encryption")
    algorithm: str = Field(default="libsodium-sealed-box", description="Encryption algorithm used")


class SessionEncryptionManager:
    """Manages per-session encryption keys and decryption operations.

    This class generates a keypair on initialization and provides methods
    to decrypt secrets. The private key is stored in memory only and
    destroyed when the session ends.
    """

    def __init__(self) -> None:
        """Initialize a new session with a fresh keypair."""
        self._private_key = PrivateKey.generate()
        self._public_key = self._private_key.public_key
        self._kid = secrets.token_urlsafe(16)
        self._sealed_box = SealedBox(self._private_key)

        logger.info(f"Generated new session keypair with kid: {self._kid}")

    @property
    def kid(self) -> str:
        """Get the key ID for this session."""
        return self._kid

    @property
    def public_key_info(self) -> SessionKeyPair:
        """Get public key information for this session.

        Returns:
            SessionKeyPair with public key and metadata
        """
        public_key_bytes = bytes(self._public_key)
        public_key_b64 = base64.b64encode(public_key_bytes).decode("ascii")

        return SessionKeyPair(
            kid=self._kid,
            public_key_b64=public_key_b64,
            algorithm="libsodium-sealed-box",
            encoding="base64",
        )

    def decrypt_secret(self, encrypted_secret: EncryptedSecret) -> str:
        """Decrypt an encrypted secret.

        Args:
            encrypted_secret: The encrypted secret payload

        Returns:
            Decrypted plaintext secret

        Raises:
            ValueError: If kid mismatch, invalid ciphertext, or decryption fails
        """
        if encrypted_secret.kid != self._kid:
            raise ValueError(f"Key ID mismatch: expected {self._kid}, got {encrypted_secret.kid}")

        if encrypted_secret.algorithm != "libsodium-sealed-box":
            raise ValueError(
                f"Unsupported algorithm: {encrypted_secret.algorithm}. "
                "Only 'libsodium-sealed-box' is supported."
            )

        try:
            ciphertext_bytes = base64.b64decode(encrypted_secret.ciphertext)
        except Exception as e:
            raise ValueError(f"Invalid base64 ciphertext: {e}") from e

        if len(ciphertext_bytes) > MAX_CIPHERTEXT_SIZE:
            raise ValueError(
                f"Ciphertext too large: {len(ciphertext_bytes)} bytes "
                f"(max {MAX_CIPHERTEXT_SIZE} bytes)"
            )

        try:
            plaintext_bytes = self._sealed_box.decrypt(ciphertext_bytes)
            plaintext = plaintext_bytes.decode("utf-8")

            self._zeroize_buffer(plaintext_bytes)

            return plaintext
        except Exception as e:
            raise ValueError(f"Decryption failed: {e}") from e

    @staticmethod
    def _zeroize_buffer(buffer: bytearray | bytes) -> None:
        """Attempt to zeroize a buffer in memory.

        Note: This is a best-effort approach. Python's memory management
        makes it difficult to guarantee complete zeroization.

        Args:
            buffer: Buffer to zeroize
        """
        if isinstance(buffer, bytearray):
            for i in range(len(buffer)):
                buffer[i] = 0
        elif isinstance(buffer, bytes):
            try:
                buffer_array = bytearray(buffer)
                for i in range(len(buffer_array)):
                    buffer_array[i] = 0
            except Exception:
                pass

    def __del__(self) -> None:
        """Clean up private key on deletion."""
        if hasattr(self, "_private_key"):
            try:
                key_bytes = bytes(self._private_key)
                self._zeroize_buffer(bytearray(key_bytes))
            except Exception:
                pass


def is_encryption_enabled() -> bool:
    """Check if session-scoped encryption is enabled.

    Returns:
        True if encryption is enabled via environment variable
    """
    return os.environ.get("CONNECTOR_BUILDER_MCP_ENABLE_ENCRYPTION", "").lower() in (
        "true",
        "1",
        "yes",
    )


def get_encryption_instructions() -> str:
    """Get user instructions for encrypting secrets.

    Returns:
        Markdown-formatted instructions
    """
    return """# Encrypting Secrets for MCP

To securely provide secrets to the connector builder:

1. **Get the public key**: Use the `get_session_public_key` resource to retrieve the session's public key.

2. **Encrypt your secret**: Use one of these methods:

   **Option A: Online Tool (Client-Side Encryption)**
   - Visit a trusted client-side encryption tool that supports libsodium sealed-box
   - Paste the public key (base64-encoded)
   - Paste your secret value
   - Copy the resulting ciphertext

   **Option B: Command Line (Python)**
   ```bash
   pip install pynacl
   python -c "
   import base64
   from nacl.public import PublicKey, SealedBox

   public_key_b64 = 'YOUR_PUBLIC_KEY_HERE'
   secret = 'YOUR_SECRET_HERE'

   public_key = PublicKey(base64.b64decode(public_key_b64))
   sealed_box = SealedBox(public_key)
   ciphertext = sealed_box.encrypt(secret.encode('utf-8'))
   print(base64.b64encode(ciphertext).decode('ascii'))
   "
   ```

3. **Use the encrypted secret**: Pass the ciphertext to MCP tools that support encrypted secrets:
   ```json
   {
     "ciphertext": "YOUR_CIPHERTEXT_HERE",
     "kid": "KEY_ID_FROM_PUBLIC_KEY",
     "algorithm": "libsodium-sealed-box"
   }
   ```

**Security Notes:**
- The session key is generated fresh for each MCP session
- Private keys are stored in memory only and destroyed when the session ends
- Plaintext secrets are never logged or persisted
- Ciphertext is limited to 64 KB
"""
