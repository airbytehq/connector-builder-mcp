# Session-Scoped Encryption for Remote Secrets (MVP)

This feature allows you to provide secrets to the Connector Builder MCP server without exposing plaintext to the LLM or persisting plaintext on the server.

## Features

- **Session-scoped keypair**: A new public/private keypair is generated for each MCP session
- **No plaintext at rest**: Secrets are decrypted only when needed and immediately discarded
- **Client-side encryption**: You encrypt secrets on your machine before sending them
- **Size limit**: Maximum ciphertext size is 64 KB
- **Algorithm**: Uses libsodium sealed-box (X25519 + XSalsa20-Poly1305)

## Enabling Session Encryption

Session encryption is **disabled by default**. To enable it, set the environment variable:

```bash
export ENABLE_SESSION_ENCRYPTION=true
```

Then start or restart your MCP server:

```bash
# For stable version from PyPI
uvx airbyte-connector-builder-mcp

# Or from source
uv run connector-builder-mcp
```

## Getting the Public Key

Once encryption is enabled, you can get encryption instructions using the MCP tool:

```
get_encryption_instructions()
```

The public key is also available as an MCP resource at:
```
mcp+session://encryption/pubkey
```

This resource returns a JSON object with:
- `kid`: Key ID for this session
- `alg`: Algorithm (libsodium-sealedbox)
- `public_key`: Base64-encoded public key
- `encoding`: Encoding format (base64)
- `max_size_bytes`: Maximum ciphertext size (65536 bytes)

## Encrypting Secrets

### Option A: Third-Party Tools (Recommended for MVP)

You can use any client-side encryption tool that supports libsodium sealed-box:

1. **Command-line with Python** (if you have PyNaCl installed):
   ```bash
   python3 -c "
   import base64
   import nacl.public
   
   # Get the public key from the MCP resource
   public_key_b64 = 'YOUR_PUBLIC_KEY_HERE'
   public_key = nacl.public.PublicKey(base64.b64decode(public_key_b64))
   sealed_box = nacl.public.SealedBox(public_key)
   
   # Enter your secret
   plaintext = input('Enter secret: ')
   ciphertext = sealed_box.encrypt(plaintext.encode('utf-8'))
   
   print('Ciphertext:', base64.b64encode(ciphertext).decode('ascii'))
   "
   ```

2. **JavaScript/Browser** (using libsodium.js):
   ```javascript
   // Load libsodium.js in your browser
   // https://github.com/jedisct1/libsodium.js
   
   await sodium.ready;
   const publicKeyBytes = sodium.from_base64(publicKeyBase64);
   const plaintext = "your-secret";
   const ciphertext = sodium.crypto_box_seal(plaintext, publicKeyBytes);
   const ciphertextBase64 = sodium.to_base64(ciphertext);
   ```

### Option B: CLI One-Liner for Power Users

If you have the connector-builder-mcp package installed:

```bash
# Install if needed
pip install airbyte-connector-builder-mcp

# Use the helper (future enhancement - see Implementation section)
```

## Using Encrypted Secrets

Once you have the ciphertext, you can use it with the secrets hydration functionality:

```python
# Example: Using hydrate_config with encrypted secrets
encrypted_secrets = {
    "api_key": {
        "ciphertext": "YOUR_BASE64_CIPHERTEXT_HERE",
        "kid": "SESSION_KID_HERE"
    },
    "credentials.password": {
        "ciphertext": "ANOTHER_BASE64_CIPHERTEXT",
        "kid": "SESSION_KID_HERE"
    }
}

# This will decrypt the secrets and merge them into the config
config = hydrate_config(base_config, encrypted_secrets=encrypted_secrets)
```

The `encrypted_secrets` parameter accepts a dictionary mapping config paths to encrypted secret objects with `ciphertext` and `kid` fields.

## Security Considerations

### What We Do

- ✅ **No logging**: Secrets are never logged
- ✅ **No persistence**: Private key lives only in memory and is destroyed on shutdown
- ✅ **Session-scoped**: Each session gets a new keypair
- ✅ **Buffer zeroization**: Plaintext buffers are cleared after use (to the extent Python allows)
- ✅ **Size limits**: Ciphertext is limited to 64 KB to prevent abuse

### What You Should Do

- 🔒 **Use HTTPS/TLS**: Always use secure connections for your MCP server
- 🔒 **Rotate secrets**: Use unique secrets per session or project
- 🔒 **Verify kid**: Always check that the `kid` matches the current session
- 🔒 **Don't share ciphertext**: Each ciphertext is tied to a specific session keypair

### Limitations

- ⚠️ **Session-bound**: Ciphertext is only valid for the current session
- ⚠️ **No persistence**: You must re-encrypt if the server restarts
- ⚠️ **Python buffer limitations**: Complete buffer zeroization is limited by Python's memory management

## Troubleshooting

### "Session encryption is not enabled"
Make sure you set `ENABLE_SESSION_ENCRYPTION=true` and restarted the server.

### "Key ID mismatch"
The session has changed or restarted. Get the new public key and re-encrypt your secret.

### "Invalid base64 ciphertext"
Check that your ciphertext is properly base64-encoded and wasn't corrupted during copy-paste.

### "Decryption failed"
The ciphertext might be invalid or encrypted with the wrong public key. Make sure you're using the public key from the current session.

### "Ciphertext too large"
Your secret is too large. The maximum size is 64 KB. Consider splitting it or using a reference/URL instead.

## Examples

### Complete Workflow

1. **Enable encryption**:
   ```bash
   export ENABLE_SESSION_ENCRYPTION=true
   uvx airbyte-connector-builder-mcp
   ```

2. **Get the public key** (via MCP tool):
   ```
   get_encryption_instructions()
   ```

3. **Encrypt your secret**:
   ```bash
   python3 -c "
   import base64
   import nacl.public
   
   public_key = nacl.public.PublicKey(base64.b64decode('sHpLmWIPfzyp8hizW9dCGpHWg4vpr71OiCvkuFsrN3o='))
   sealed_box = nacl.public.SealedBox(public_key)
   plaintext = 'my-api-key-12345'
   ciphertext = sealed_box.encrypt(plaintext.encode('utf-8'))
   print(base64.b64encode(ciphertext).decode('ascii'))
   "
   ```

4. **Use the encrypted secret**:
   ```python
   encrypted_secrets = {
       "api_key": {
           "ciphertext": "XtsqwzTEURX1kbwb6htoRjUdTVpaSBXjIyZ/NMAg83pkDpEiNqsYkgdNyNxmx3ntK+d1Nrrt95uHq6I=",
           "kid": "sHpLmWIPfzw"
       }
   }
   
   config = hydrate_config({"host": "api.example.com"}, encrypted_secrets=encrypted_secrets)
   # Result: {"host": "api.example.com", "api_key": "my-api-key-12345"}
   ```

## Implementation Details

- **Algorithm**: libsodium sealed-box (X25519 key exchange + XSalsa20-Poly1305 authenticated encryption)
- **Key size**: 32 bytes (X25519 public key)
- **Overhead**: ~48 bytes (nonce + MAC)
- **Library**: PyNaCl (Python bindings for libsodium)
- **Feature flag**: `ENABLE_SESSION_ENCRYPTION` (off by default)

## Future Enhancements (Not in MVP)

- 🚧 Hosting our own encryption webapp
- 🚧 Durable secret storage (encrypted at rest)
- 🚧 Multi-session secret reuse
- 🚧 Alternative algorithms (JWE, age, etc.)
