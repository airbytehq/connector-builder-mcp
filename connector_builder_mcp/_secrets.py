"""Secrets management for connector configurations using dotenv files and privatebin URLs.

This module provides stateless tools for managing secrets in .env files and privatebin URLs without
exposing actual secret values to the LLM. All functions require explicit dotenv
file paths or privatebin URLs to be passed by the caller.
"""

import logging
import os
from io import StringIO
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import urlparse

import privatebin
import requests
from dotenv import dotenv_values, set_key
from fastmcp import FastMCP
from pydantic import BaseModel, Field

from connector_builder_mcp._guidance import DOTENV_FILE_URI_DESCRIPTION
from connector_builder_mcp._util import parse_manifest_input


logger = logging.getLogger(__name__)


def _privatebin_password_exists() -> bool:
    """Check if PRIVATEBIN_PASSWORD environment variable exists.

    Returns:
        True if PRIVATEBIN_PASSWORD is set, False otherwise
    """
    return bool(os.getenv("PRIVATEBIN_PASSWORD"))


def _is_privatebin_url(url: str) -> bool:
    """Check if a URL is a privatebin URL by domain pattern.
    
    Args:
        url: URL to check
        
    Returns:
        True if URL is a privatebin URL, False otherwise
    """
    if not isinstance(url, str):
        return False
        
    if url.startswith("https://"):
        parsed = urlparse(url)
        return "privatebin" in parsed.netloc.lower()
    
    return False


def _get_privatebin_password() -> str | None:
    """Get PRIVATEBIN_PASSWORD environment variable value.

    Returns:
        PRIVATEBIN_PASSWORD value or None if not set
    """
    return os.getenv("PRIVATEBIN_PASSWORD")


class SecretInfo(BaseModel):
    """Information about a secret without exposing its value."""

    key: str
    is_set: bool


class SecretsFileInfo(BaseModel):
    """Information about the secrets file and its contents."""

    file_path: str
    exists: bool
    secrets: list[SecretInfo]


def _parse_secrets_uris(dotenv_file_uris: str | list[str] | None) -> list[str]:
    """Parse secrets URIs from various input formats.

    Args:
        dotenv_file_uris: String, comma-separated string, or list of URIs

    Returns:
        List of URI strings
    """
    if not dotenv_file_uris:
        return []

    if isinstance(dotenv_file_uris, str):
        if "," in dotenv_file_uris:
            return [uri.strip() for uri in dotenv_file_uris.split(",") if uri.strip()]
        return [dotenv_file_uris]

    return dotenv_file_uris


def _validate_secrets_uris(dotenv_file_uris: str | list[str] | None) -> list[str]:
    """Validate secrets URIs and return array of error messages.

    Args:
        dotenv_file_uris: String, comma-separated string, or list of URIs

    Returns:
        List of error messages (empty if all valid)
    """
    errors: list[str] = []
    uris = _parse_secrets_uris(dotenv_file_uris)

    if not uris:
        return errors

    for uri in uris:
        if uri.startswith(("http:", "https:")):
            if _is_privatebin_url(uri):
                if not _privatebin_password_exists():
                    errors.append(
                        f"Privatebin URL '{uri}' requires PRIVATEBIN_PASSWORD environment variable to be set"
                    )
                parsed = urlparse(uri)
                if "password=" in parsed.query:
                    errors.append(
                        f"Privatebin URL '{uri}' contains embedded password - this is not allowed for security reasons. You must relaunch the MCP server with an included `PRIVATEBIN_PASSWORD` env var."
                    )

            else:
                raise ValueError(f"Invalid privatebin URL: {uri}")

        elif ":" in uri.split("/", 1)[0] and not uri.startswith("file://"):
            raise ValueError(f"Invalid URI format: {uri}")

        else:
            # Assume local file path
            path_obj = Path(uri)
            if not path_obj.is_absolute():
                errors.append(f"Local file path must be absolute, got relative path: {uri}")

    return errors


def _fetch_privatebin_content(url: str) -> str:
    """Fetch content from privatebin URL with password authentication.

    Args:
        url: Privatebin URL (e.g., https://privatebin.net/...)

    Returns:
        Content as string, empty string on error
    """
    try:
        if not _is_privatebin_url(url):
            return ""

        https_url = url

        password = _get_privatebin_password()
        if not password:
            logger.error("PRIVATEBIN_PASSWORD environment variable not set")
            return ""

        if "privatebin.net" in https_url:
            paste = privatebin.get(https_url, password=password)
            return paste.text
        else:
            parsed = urlparse(https_url)
            if "password=" not in parsed.query:
                separator = "&" if parsed.query else "?"
                https_url = f"{https_url}{separator}password={password}"

            response = requests.get(https_url, timeout=30)
            response.raise_for_status()
            return response.text

    except Exception as e:
        logger.error(f"Error fetching privatebin content from {url}: {e}")
        return ""


def load_secrets(dotenv_file_uris: str | list[str] | None = None) -> dict[str, str]:
    """Load secrets from the specified dotenv files and privatebin URLs.

    Args:
        dotenv_file_uris: List of paths/URLs to .env files or privatebin URLs,
                              or comma-separated string, or single string

    Returns:
        Dictionary of secret key-value pairs from all sources
    """
    validation_errors = _validate_secrets_uris(dotenv_file_uris)
    if validation_errors:
        for error in validation_errors:
            logger.error(f"Validation error: {error}")
        return {}

    uris = _parse_secrets_uris(dotenv_file_uris)
    if not uris:
        return {}

    all_secrets = {}

    for uri in uris:
        try:
            if _is_privatebin_url(uri):
                content = _fetch_privatebin_content(uri)
                if content:
                    secrets = dotenv_values(stream=StringIO(content))
                    if secrets:
                        filtered_secrets = {k: v for k, v in secrets.items() if v is not None}
                        all_secrets.update(filtered_secrets)
                        logger.info(f"Loaded {len(filtered_secrets)} secrets from privatebin URL")
            else:
                if not Path(uri).exists():
                    logger.warning(f"Secrets file not found: {uri}")
                    continue

                secrets = dotenv_values(uri)
                if secrets:
                    filtered_secrets = {k: v for k, v in secrets.items() if v is not None}
                    all_secrets.update(filtered_secrets)
                    logger.info(f"Loaded {len(filtered_secrets)} secrets from {uri}")

        except Exception as e:
            logger.error(f"Error loading secrets from {uri}: {e}")
            continue

    return all_secrets


def hydrate_config(
    config: dict[str, Any], dotenv_file_uris: str | list[str] | None = None
) -> dict[str, Any]:
    """Hydrate configuration with secrets from dotenv files and privatebin URLs using dot notation.

    Dotenv keys are mapped directly to config paths using dot notation:
    - credentials.password -> credentials.password
    - api_key -> api_key
    - oauth.client_secret -> oauth.client_secret

    Args:
        config: Configuration dictionary to hydrate with secrets
        dotenv_file_uris: List of paths/URLs to .env files or privatebin URLs,
                              or comma-separated string, or single string

    Returns:
        Configuration with secrets injected from .env files and privatebin URLs
    """
    if not config or not dotenv_file_uris:
        return config

    secrets = load_secrets(dotenv_file_uris)
    if not secrets:
        return config

    def _set_nested_value(obj: dict[str, Any], path: list[str], value: str) -> None:
        """Set a nested value in a dictionary using a path."""
        current = obj
        for key in path[:-1]:
            if key not in current:
                current[key] = {}
            elif not isinstance(current[key], dict):
                return
            current = current[key]
        current[path[-1]] = value

    result = config.copy()

    for dotenv_key, secret_value in secrets.items():
        if secret_value and not secret_value.startswith("#"):
            path = dotenv_key.split(".")
            _set_nested_value(result, path, secret_value)

    return result


def list_dotenv_secrets(
    dotenv_path: Annotated[
        str,
        Field(description=DOTENV_FILE_URI_DESCRIPTION.strip()),
    ],
) -> SecretsFileInfo:
    """List all secrets in the specified dotenv files and privatebin URLs without exposing values.

    Args:
        dotenv_file_uris: Path to .env file or privatebin URL, or list of paths/URLs, or comma-separated string

    Returns:
        Information about the secrets files and their contents
    """
    import sys
    print(f"DEBUG list_dotenv_secrets: received dotenv_path='{dotenv_path}', type={type(dotenv_path)}", file=sys.stderr)
    
    if isinstance(dotenv_path, str) and dotenv_path.startswith("/home/ubuntu/https:/"):
        print(f"DEBUG list_dotenv_secrets: applying workaround, before='{dotenv_path}'", file=sys.stderr)
        dotenv_path = dotenv_path.replace("/home/ubuntu/https:/", "https://")
        print(f"DEBUG list_dotenv_secrets: after workaround='{dotenv_path}'", file=sys.stderr)
    
    validation_errors = _validate_secrets_uris(dotenv_path)
    if validation_errors:
        error_message = "; ".join(validation_errors)
        return SecretsFileInfo(
            file_path=f"Validation failed: {error_message}", exists=False, secrets=[]
        )

    uris = _parse_secrets_uris(dotenv_path)
    if not uris:
        return SecretsFileInfo(file_path="", exists=False, secrets=[])

    if len(uris) == 1:
        uri = uris[0]
        secrets_info = []

        if _is_privatebin_url(uri):
            content = _fetch_privatebin_content(uri)
            if content:
                try:
                    secrets = dotenv_values(stream=StringIO(content))
                    for key, value in (secrets or {}).items():
                        secrets_info.append(
                            SecretInfo(
                                key=key,
                                is_set=bool(value and value.strip()),
                            )
                        )
                except Exception as e:
                    logger.error(f"Error reading privatebin secrets: {e}")

            return SecretsFileInfo(file_path=uri, exists=bool(content), secrets=secrets_info)
        else:
            file_path = Path(uri)
            if file_path.exists():
                try:
                    secrets = dotenv_values(uri)
                    for key, value in (secrets or {}).items():
                        secrets_info.append(
                            SecretInfo(
                                key=key,
                                is_set=bool(value and value.strip()),
                            )
                        )
                except Exception as e:
                    logger.error(f"Error reading secrets file: {e}")

            return SecretsFileInfo(
                file_path=str(file_path.absolute()), exists=file_path.exists(), secrets=secrets_info
            )

    all_secrets = load_secrets(dotenv_path)
    secrets_info = []
    for key, value in all_secrets.items():
        secrets_info.append(
            SecretInfo(
                key=key,
                is_set=bool(value and value.strip()),
            )
        )

    return SecretsFileInfo(
        file_path=f"Multiple sources: {', '.join(uris)}",
        exists=bool(all_secrets),
        secrets=secrets_info,
    )


def populate_dotenv_missing_secrets_stubs(
    dotenv_path: Annotated[
        str,
        Field(
            description="Absolute path to the .env file to add secrets to, or privatebin URL to check. "
            + DOTENV_FILE_URI_DESCRIPTION.strip()
        ),
    ],
    manifest: Annotated[
        str | None,
        Field(
            description="Connector manifest to analyze for secrets. Can be raw YAML content or path to YAML file"
        ),
    ] = None,
    config_paths: Annotated[
        str | None,
        Field(
            description="Comma-separated list of config paths like "
            "'credentials.password,oauth.client_secret'"
        ),
    ] = None,
    allow_create: Annotated[bool, Field(description="Create the file if it doesn't exist")] = True,
) -> str:
    """Add secret stubs to the specified dotenv file for the user to fill in, or check privatebin URLs.

    Supports two modes:
    1. Manifest-based: Pass manifest to auto-detect secrets from connection_specification
    2. Path-based: Pass config_paths list like 'credentials.password,oauth.client_secret'

    If both are provided, both sets of secrets will be added.

    For local files: This function is non-destructive and will not overwrite existing secrets.
    For privatebin URLs: This function will check existing secrets and return instructions for manual updates.

    Returns:
        Message about the operation result
    """
    if isinstance(dotenv_path, str) and dotenv_path.startswith("/home/ubuntu/https:/"):
        dotenv_path = dotenv_path.replace("/home/ubuntu/https:/", "https://")
    
    validation_errors = _validate_secrets_uris(dotenv_path)
    if validation_errors:
        return f"Validation failed: {'; '.join(validation_errors)}"

    if _is_privatebin_url(dotenv_path):
        config_paths_list = config_paths.split(",") if config_paths else []
        if not any([manifest, config_paths_list]):
            return "Error: Must provide either manifest or config_paths"

        secrets_to_add = []

        if manifest:
            manifest_dict = parse_manifest_input(manifest)
            secrets_to_add.extend(_extract_secrets_names_from_manifest(manifest_dict))

        if config_paths_list:
            for path in config_paths_list:
                dotenv_key = _config_path_to_dotenv_key(path)
                secrets_to_add.append(dotenv_key)

        if not secrets_to_add:
            return "No secrets found to add"

        existing_secrets = load_secrets(dotenv_path)

        secrets_info = []
        for key, value in existing_secrets.items():
            secrets_info.append(
                SecretInfo(
                    key=key,
                    is_set=_is_secret_set(value),
                )
            )

        existing_keys = set(existing_secrets.keys())
        missing_keys = [key for key in secrets_to_add if key not in existing_keys]
        existing_requested_keys = [key for key in secrets_to_add if key in existing_keys]

        result_parts = []

        if existing_requested_keys:
            existing_summary = [
                f"{key}({'set' if _is_secret_set(existing_secrets.get(key, '')) else 'unset'})"
                for key in existing_requested_keys
            ]
            result_parts.append(f"Existing secrets found: {', '.join(existing_summary)}")

        if missing_keys:
            result_parts.append(f"Missing secrets: {', '.join(missing_keys)}")
            result_parts.append(
                "Instructions: Privatebin URLs are immutable. To add missing secrets:"
            )
            result_parts.append("1. Create a new privatebin with the missing secrets")
            result_parts.append("2. Set a password for the privatebin")
            result_parts.append("3. Use the new privatebin URL (HTTPS format is supported)")
            result_parts.append("4. Ensure PRIVATEBIN_PASSWORD environment variable is set")

        if not missing_keys and existing_requested_keys:
            result_parts.append("All requested secrets are already present in the privatebin.")

        return " ".join(result_parts)

    path_obj = Path(dotenv_path)
    config_paths_list = config_paths.split(",") if config_paths else []
    if not any([manifest, config_paths_list]):
        return "Error: Must provide either manifest or config_paths"

    try:
        if allow_create:
            path_obj.parent.mkdir(parents=True, exist_ok=True)
            path_obj.touch()
        elif not path_obj.exists():
            return f"Error: File {dotenv_path} does not exist and allow_create=False"

        secrets_to_add = []

        if manifest:
            manifest_dict = parse_manifest_input(manifest)
            secrets_to_add.extend(_extract_secrets_names_from_manifest(manifest_dict))

        if config_paths_list:
            for path in config_paths_list:
                dotenv_key = _config_path_to_dotenv_key(path)
                secrets_to_add.append(dotenv_key)

        if not secrets_to_add:
            return "No secrets found to add"

        local_existing_secrets: dict[str, str] = {}
        if path_obj.exists():
            try:
                raw_secrets = dotenv_values(dotenv_path) or {}
                local_existing_secrets = {k: v for k, v in raw_secrets.items() if v is not None}
            except Exception as e:
                logger.error(f"Error reading existing secrets: {e}")

        collisions = [key for key in secrets_to_add if key in local_existing_secrets]
        if collisions:
            secrets_info = []
            for key, value in local_existing_secrets.items():
                secrets_info.append(
                    SecretInfo(
                        key=key,
                        is_set=_is_secret_set(value),
                    )
                )

            collision_list = ", ".join(collisions)
            existing_secrets_summary = [
                f"{s.key}({'set' if s.is_set else 'unset'})" for s in secrets_info
            ]
            return f"Error: Cannot create stubs for secrets that already exist: {collision_list}. Existing secrets in file: {', '.join(existing_secrets_summary)}"

        added_count = 0
        for dotenv_key in secrets_to_add:
            placeholder_value = f"# TODO: Set actual value for {dotenv_key}"
            set_key(dotenv_path, dotenv_key, placeholder_value)
            added_count += 1

        return f"Added {added_count} secret stub(s) to {dotenv_path}: {', '.join(secrets_to_add)}. Please set the actual values."

    except Exception as e:
        logger.error(f"Error adding secret stubs: {e}")
        return f"Error adding secret stubs: {str(e)}"


def _extract_secrets_names_from_manifest(manifest: dict[str, Any]) -> list[str]:
    """Extract secret fields from manifest connection specification.

    Args:
        manifest: Connector manifest dictionary

    Returns:
        List of dotenv key names
    """
    secrets = []

    try:
        spec = manifest.get("spec", {})
        connection_spec = spec.get("connection_specification", {})
        properties = connection_spec.get("properties", {})

        for field_name, field_spec in properties.items():
            if field_spec.get("airbyte_secret", False):
                dotenv_key = _config_path_to_dotenv_key(field_name)
                secrets.append(dotenv_key)

    except Exception as e:
        logger.warning(f"Error extracting secrets from manifest: {e}")

    return secrets


def _is_secret_set(value: str | None) -> bool:
    """Check if a secret value is considered 'set' (not empty, not a comment).

    Args:
        value: The secret value to check

    Returns:
        True if the secret is set, False otherwise
    """
    return bool(value and value.strip() and not value.strip().startswith("#"))


def _config_path_to_dotenv_key(config_path: str) -> str:
    """Convert config path to dotenv key (keeping original format).

    Examples:
    - 'credentials.password' -> 'credentials.password'
    - 'api_key' -> 'api_key'
    - 'oauth.client_secret' -> 'oauth.client_secret'

    Args:
        config_path: Dot-separated config path

    Returns:
        Dotenv key name (same as input)
    """
    return config_path


def register_secrets_tools(app: FastMCP) -> None:
    """Register secrets management tools with the FastMCP app.

    Args:
        app: FastMCP application instance
    """
    app.tool(list_dotenv_secrets)
    app.tool(populate_dotenv_missing_secrets_stubs)
