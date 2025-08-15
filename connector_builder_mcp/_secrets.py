"""Secrets management for connector configurations using dotenv files and pastebin URLs.

This module provides stateless tools for managing secrets in .env files and pastebin URLs without
exposing actual secret values to the LLM. All functions require explicit dotenv
file paths or pastebin URLs to be passed by the caller.
"""

import logging
import os
from io import StringIO
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import urlparse

import requests
from dotenv import dotenv_values, set_key
from fastmcp import FastMCP
from pydantic import BaseModel, Field

from connector_builder_mcp._util import parse_manifest_input


logger = logging.getLogger(__name__)


class SecretInfo(BaseModel):
    """Information about a secret without exposing its value."""

    key: str
    is_set: bool


class SecretsFileInfo(BaseModel):
    """Information about the secrets file and its contents."""

    file_path: str
    exists: bool
    secrets: list[SecretInfo]


def _parse_secrets_uris(secrets_env_file_uris: str | list[str] | None) -> list[str]:
    """Parse secrets URIs from various input formats.

    Args:
        secrets_env_file_uris: String, comma-separated string, or list of URIs

    Returns:
        List of URI strings
    """
    if not secrets_env_file_uris:
        return []

    if isinstance(secrets_env_file_uris, str):
        if "," in secrets_env_file_uris:
            return [uri.strip() for uri in secrets_env_file_uris.split(",") if uri.strip()]
        return [secrets_env_file_uris]

    return secrets_env_file_uris


def _fetch_pastebin_content(url: str) -> str:
    """Fetch content from pastebin URL with password authentication.

    Args:
        url: Pastebin URL (e.g., pastebin://pastebin.com/abc123?password=xyz)

    Returns:
        Content as string, empty string on error
    """
    try:
        if not url.startswith("pastebin://"):
            return ""

        https_url = url.replace("pastebin://", "https://", 1)

        password = os.getenv("PASTEBIN_PASSWORD")
        if not password:
            logger.error("PASTEBIN_PASSWORD environment variable not set")
            return ""

        parsed = urlparse(https_url)
        if "password=" not in parsed.query:
            separator = "&" if parsed.query else "?"
            https_url = f"{https_url}{separator}password={password}"

        response = requests.get(https_url, timeout=30)
        response.raise_for_status()
        return response.text

    except Exception as e:
        logger.error(f"Error fetching pastebin content from {url}: {e}")
        return ""


def load_secrets(secrets_env_file_uris: str | list[str] | None = None) -> dict[str, str]:
    """Load secrets from the specified dotenv files and pastebin URLs.

    Args:
        secrets_env_file_uris: List of paths/URLs to .env files or pastebin URLs,
                              or comma-separated string, or single string

    Returns:
        Dictionary of secret key-value pairs from all sources
    """
    uris = _parse_secrets_uris(secrets_env_file_uris)
    if not uris:
        return {}

    all_secrets = {}

    for uri in uris:
        try:
            if uri.startswith("pastebin://"):
                content = _fetch_pastebin_content(uri)
                if content:
                    secrets = dotenv_values(stream=StringIO(content))
                    if secrets:
                        filtered_secrets = {k: v for k, v in secrets.items() if v is not None}
                        all_secrets.update(filtered_secrets)
                        logger.info(f"Loaded {len(filtered_secrets)} secrets from pastebin URL")
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
    config: dict[str, Any], secrets_env_file_uris: str | list[str] | None = None
) -> dict[str, Any]:
    """Hydrate configuration with secrets from dotenv files and pastebin URLs using dot notation.

    Dotenv keys are mapped directly to config paths using dot notation:
    - credentials.password -> credentials.password
    - api_key -> api_key
    - oauth.client_secret -> oauth.client_secret

    Args:
        config: Configuration dictionary to hydrate with secrets
        secrets_env_file_uris: List of paths/URLs to .env files or pastebin URLs,
                              or comma-separated string, or single string

    Returns:
        Configuration with secrets injected from .env files and pastebin URLs
    """
    if not config or not secrets_env_file_uris:
        return config

    secrets = load_secrets(secrets_env_file_uris)
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
    secrets_env_file_uris: Annotated[
        str | list[str],
        Field(
            description="Path to .env file or pastebin URL, or list of paths/URLs, or comma-separated string"
        ),
    ],
) -> SecretsFileInfo:
    """List all secrets in the specified dotenv files and pastebin URLs without exposing values.

    Args:
        secrets_env_file_uris: Path to .env file or pastebin URL, or list of paths/URLs, or comma-separated string

    Returns:
        Information about the secrets files and their contents
    """
    uris = _parse_secrets_uris(secrets_env_file_uris)
    if not uris:
        return SecretsFileInfo(file_path="", exists=False, secrets=[])

    if len(uris) == 1:
        uri = uris[0]
        secrets_info = []

        if uri.startswith("pastebin://"):
            content = _fetch_pastebin_content(uri)
            if content:
                try:
                    from io import StringIO

                    secrets = dotenv_values(stream=StringIO(content))
                    for key, value in (secrets or {}).items():
                        secrets_info.append(
                            SecretInfo(
                                key=key,
                                is_set=bool(value and value.strip()),
                            )
                        )
                except Exception as e:
                    logger.error(f"Error reading pastebin secrets: {e}")

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

    all_secrets = load_secrets(secrets_env_file_uris)
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
    secrets_env_file_uris: Annotated[
        str,
        Field(
            description="Absolute path to the .env file to add secrets to, or pastebin URL to check"
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
    """Add secret stubs to the specified dotenv file for the user to fill in, or check pastebin URLs.

    Supports two modes:
    1. Manifest-based: Pass manifest to auto-detect secrets from connection_specification
    2. Path-based: Pass config_paths list like 'credentials.password,oauth.client_secret'

    If both are provided, both sets of secrets will be added.

    For local files: This function is non-destructive and will not overwrite existing secrets.
    For pastebin URLs: This function will check existing secrets and return instructions for manual updates.

    Returns:
        Message about the operation result
    """
    if secrets_env_file_uris.startswith("pastebin://"):
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

        existing_secrets = load_secrets(secrets_env_file_uris)

        secrets_info = []
        for key, value in existing_secrets.items():
            secrets_info.append(
                SecretInfo(
                    key=key,
                    is_set=bool(value and value.strip() and not value.strip().startswith("#")),
                )
            )

        existing_keys = set(existing_secrets.keys())
        missing_keys = [key for key in secrets_to_add if key not in existing_keys]
        existing_requested_keys = [key for key in secrets_to_add if key in existing_keys]

        result_parts = []

        if existing_requested_keys:
            existing_summary = [
                f"{key}({'set' if existing_secrets.get(key, '').strip() and not existing_secrets.get(key, '').strip().startswith('#') else 'unset'})"
                for key in existing_requested_keys
            ]
            result_parts.append(f"Existing secrets found: {', '.join(existing_summary)}")

        if missing_keys:
            result_parts.append(f"Missing secrets: {', '.join(missing_keys)}")
            result_parts.append(
                "Instructions: Pastebin URLs are immutable. To add missing secrets:"
            )
            result_parts.append("1. Create a new pastebin with the missing secrets")
            result_parts.append("2. Set a password for the pastebin")
            result_parts.append("3. Use the new pastebin URL with pastebin:// scheme")
            result_parts.append("4. Ensure PASTEBIN_PASSWORD environment variable is set")

        if not missing_keys and existing_requested_keys:
            result_parts.append("All requested secrets are already present in the pastebin.")

        return " ".join(result_parts)

    path_obj = Path(secrets_env_file_uris)
    if not path_obj.is_absolute():
        return f"Error: Path must be absolute, got relative path: {secrets_env_file_uris}"

    config_paths_list = config_paths.split(",") if config_paths else []
    if not any([manifest, config_paths_list]):
        return "Error: Must provide either manifest or config_paths"

    try:
        if allow_create:
            path_obj.parent.mkdir(parents=True, exist_ok=True)
            path_obj.touch()
        elif not path_obj.exists():
            return f"Error: File {secrets_env_file_uris} does not exist and allow_create=False"

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
                raw_secrets = dotenv_values(secrets_env_file_uris) or {}
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
                        is_set=bool(value and value.strip() and not value.strip().startswith("#")),
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
            set_key(secrets_env_file_uris, dotenv_key, placeholder_value)
            added_count += 1

        return f"Added {added_count} secret stub(s) to {secrets_env_file_uris}: {', '.join(secrets_to_add)}. Please set the actual values."

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
