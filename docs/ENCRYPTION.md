# Session-Scoped Encryption for Remote Secrets

This document describes the session-scoped public/private key encryption feature for securely handling remote secrets in the Connector Builder MCP server.

## Overview

The encryption feature allows users to securely provide secrets to the MCP server without exposing plaintext to the LLM or persisting plaintext on the server. Each MCP session generates a unique keypair, and secrets are encrypted client-side before being sent to the server.

## Security Model

- **Per-session keypairs**: A fresh keypair is generated for each MCP session
- **Memory-only storage**: Private keys are stored in memory only and destroyed when the session ends
- **No plaintext persistence**: Plaintext secrets are never logged or persisted to disk
- **Decrypt-on-use**: Secrets are decrypted only when needed and buffers are zeroized after use
- **Size limits**: Ciphertext is limited to 64 KB to prevent abuse

## Encryption Algorithm

The feature uses **libsodium sealed-box** (X25519 + XSalsa20-Poly1305) for encryption. This algorithm was chosen for:
- Simplicity and ease of use
- Wide client-side support (WebCrypto, command-line tools)
- Strong security guarantees
- Copy-paste friendliness for users

## Enabling Encryption

The encryption feature is **disabled by default** and must be explicitly enabled via environment variable:

```bash
export CONNECTOR_BUILDER_MCP_ENABLE_ENCRYPTION=true
```

Accepted values: `true`, `1`, `yes` (case-insensitive)

## Usage

### 1. Get the Session Public Key

When encryption is enabled, the MCP server exposes a resource containing the session's public key:

**Resource URI**: `session://encryption/public-key`

**Response format**:
```json
{
  "kid": "unique-session-key-id",
  "public_key_b64": "base64-encoded-public-key",
  "algorithm": "libsodium-sealed-box",
  "encoding": "base64"
}
```

### 2. Encrypt Your Secret

You can encrypt secrets using one of these methods:

#### Option A: Python Command Line

```bash
pip install pynacl

python -c "
import base64
from nacl.public import PublicKey, SealedBox

# Replace with your values
public_key_b64 = 'YOUR_PUBLIC_KEY_HERE'
secret = 'YOUR_SECRET_HERE'

public_key = PublicKey(base64.b64decode(public_key_b64))
sealed_box = SealedBox(public_key)
ciphertext = sealed_box.encrypt(secret.encode('utf-8'))
print(base64.b64encode(ciphertext).decode('ascii'))
"
```

#### Option B: Python Script

```python
import base64
import json
from nacl.public import PublicKey, SealedBox

# Get public key from MCP resource
public_key_info = {
    "kid": "...",
    "public_key_b64": "...",
    "algorithm": "libsodium-sealed-box"
}

# Your secret configuration
config = {
    "api_key": "secret-key-123",
    "base_url": "https://api.example.com"
}

# Encrypt
config_json = json.dumps(config)
public_key = PublicKey(base64.b64decode(public_key_info["public_key_b64"]))
sealed_box = SealedBox(public_key)
ciphertext = sealed_box.encrypt(config_json.encode('utf-8'))
ciphertext_b64 = base64.b64encode(ciphertext).decode('ascii')

# Create encrypted secret payload
encrypted_secret = {
    "ciphertext": ciphertext_b64,
    "kid": public_key_info["kid"],
    "algorithm": "libsodium-sealed-box"
}

print(json.dumps(encrypted_secret, indent=2))
```

#### Option C: Third-Party Client-Side Encryption Tools

You can use any client-side encryption tool that supports libsodium sealed-box:
1. Visit a trusted client-side encryption tool
2. Paste the public key (base64-encoded)
3. Paste your secret value
4. Copy the resulting ciphertext

**Note**: Ensure the tool performs encryption entirely in the browser (client-side) and does not send data to a server.

### 3. Use the Encrypted Secret

Pass the encrypted secret to MCP tools that support encryption:

```json
{
  "manifest": { ... },
  "encrypted_config": {
    "ciphertext": "YOUR_CIPHERTEXT_HERE",
    "kid": "KEY_ID_FROM_PUBLIC_KEY",
    "algorithm": "libsodium-sealed-box"
  },
  "stream_name": "users",
  "max_records": 10
}
```

## Available Tools

When encryption is enabled, the following tools and resources are available:

### Resources

- **`session://encryption/public-key`**: Get the session's public key information
- **`session://encryption/instructions`**: Get detailed encryption instructions

### Tools

- **`execute_stream_test_read_with_encrypted_config`**: Test a connector stream with encrypted configuration
  - Parameters:
    - `manifest`: The connector manifest (dict)
    - `encrypted_config`: Encrypted configuration (dict with ciphertext, kid, algorithm)
    - `stream_name`: Name of the stream to test (string)
    - `max_records`: Maximum records to read (int, default: 10)

## Error Handling

The encryption system provides clear error messages for common issues:

- **Key ID mismatch**: The `kid` in the encrypted secret doesn't match the session's key
- **Invalid algorithm**: Only `libsodium-sealed-box` is supported
- **Invalid base64**: The ciphertext is not valid base64-encoded data
- **Decryption failed**: The ciphertext is corrupted or was encrypted with a different key
- **Ciphertext too large**: The ciphertext exceeds the 64 KB size limit

## Security Considerations

### What This Feature Provides

✅ Protection from LLM exposure of plaintext secrets  
✅ No plaintext persistence on the server  
✅ Session-scoped keys (destroyed after session ends)  
✅ Client-side encryption (user controls the encryption process)  
✅ Size limits to prevent abuse  

### What This Feature Does NOT Provide

❌ Durable secret storage (secrets are not persisted)  
❌ Secret management across sessions (new keys per session)  
❌ Protection from compromised client (user must encrypt securely)  
❌ Audit logging of secret usage  

### Best Practices

1. **Use trusted encryption tools**: Only use client-side encryption tools you trust
2. **Verify the public key**: Always get the public key from the MCP resource
3. **One-time use**: Treat encrypted secrets as one-time use per session
4. **Secure your environment**: Ensure your local environment is secure when encrypting secrets
5. **Don't share ciphertext**: Encrypted secrets are session-specific and cannot be reused

## Implementation Details

### Key Generation

- Uses libsodium's `PrivateKey.generate()` to create X25519 keypairs
- Key ID (`kid`) is generated using `secrets.token_urlsafe(16)`
- Public key is base64-encoded for easy transport

### Decryption Flow

1. Validate `kid` matches the session's key
2. Validate algorithm is `libsodium-sealed-box`
3. Decode base64 ciphertext
4. Check size limit (64 KB)
5. Decrypt using libsodium sealed-box
6. Decode UTF-8 plaintext
7. Zeroize plaintext bytes buffer (best effort)
8. Return plaintext string

### Buffer Zeroization

The implementation attempts to zeroize plaintext buffers after use. However, due to Python's memory management, complete zeroization cannot be guaranteed. This is a best-effort security measure.

## Testing

Comprehensive unit tests are provided in `tests/test_encryption.py`:

- Key generation and initialization
- Encrypt/decrypt roundtrip
- Error handling (wrong kid, invalid ciphertext, oversized data)
- Feature flag behavior
- JSON configuration encryption

Run tests:
```bash
pytest tests/test_encryption.py -v
```

## Future Enhancements

Potential future improvements (not in MVP):

- Hosted encryption webapp for easier client-side encryption
- Support for additional encryption algorithms (JWE)
- Durable secret storage with ciphertext persistence
- Secret rotation and key management
- Audit logging of secret usage
- Integration with secret management services

## References

- [libsodium documentation](https://doc.libsodium.org/)
- [PyNaCl documentation](https://pynacl.readthedocs.io/)
- [Sealed boxes](https://doc.libsodium.org/public-key_cryptography/sealed_boxes)
