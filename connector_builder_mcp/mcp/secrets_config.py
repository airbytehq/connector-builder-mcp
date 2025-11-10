# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Secrets management for connector configurations using dotenv files and privatebin URLs.

This module provides stateless tools for managing secrets in .env files and privatebin URLs without
exposing actual secret values to the LLM. All functions require explicit dotenv
file paths or privatebin URLs to be passed by the caller.
"""

import json
import logging
import os
from io import StringIO
from pathlib import Path
from typing import Annotated, Any, cast
from urllib.parse import urlparse

import privatebin
import requests
from dotenv import dotenv_values, set_key
from fastmcp import FastMCP
from pydantic import BaseModel, Field

from connector_builder_mcp._guidance.prompts import DOTENV_FILE_URI_DESCRIPTION
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


def _load_secrets(dotenv_file_uris: str | list[str] | None = None) -> dict[str, str]:
    """Load secrets from the specified dotenv files and privatebin URLs.

    Args:
        dotenv_file_uris: List of paths/URLs to .env files or privatebin URLs,
                              or comma-separated string, or single string

    Returns:
        Dictionary of secret key-value pairs from all sources.
        Result may be a nested dictionary, e.g. {"credentials": {"password": "secret123"}}
    """
    validation_errors: list[str] = _validate_secrets_uris(dotenv_file_uris)
    if validation_errors:
        for error in validation_errors:
            logger.error(f"Validation error: {error}")
        return {}

    uris = _parse_secrets_uris(dotenv_file_uris)
    if not uris:
        return {}

    all_secrets = {}

    for uri in uris:
        if _is_privatebin_url(uri):
            content = _fetch_privatebin_content(uri)
            if content:
                secrets = dotenv_values(stream=StringIO(content))
                if secrets:
                    filtered_secrets = {k: v for k, v in secrets.items() if v is not None}
                    all_secrets.update(filtered_secrets)
                    logger.info(f"Loaded {len(filtered_secrets)} secrets from privatebin URL")
        else:
            path = Path(uri)
            if not path.exists():
                logger.error(f"Secrets file not found: {uri}")
                raise FileNotFoundError(f"Secrets file not found: {uri}")

            secrets = dotenv_values(uri)
            if secrets:
                count = 0
                for key_path, value in {
                    k: v
                    for k, v in secrets.items()
                    if (
                        v is not None
                        and v != ""  # noqa: PLC1901 # skipping empty strings, but not 0
                        and not k.startswith("#")
                        and not v.startswith("#")
                    )
                }.items():
                    count += 1
                    _set_nested_value(all_secrets, key_path, value)

                logger.info(f"Loaded {count} secrets from {uri}")

    return all_secrets


def _set_nested_value(obj: dict[str, Any], path_str: str, value: str) -> None:
    """Set a nested value in a dictionary using a path string."""
    path = path_str.split(".")
    current = obj
    for key in path[:-1]:
        if key not in current:
            current[key] = {}
        elif not isinstance(current[key], dict):
            return
        current = current[key]
    current[path[-1]] = value


def _merge_nested_dicts(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Merge two nested dictionaries."""
    merged: dict[str, Any] = a.copy()
    for key, value in b.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _merge_nested_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def _cast_value_to_type(value: str, schema_type: str, schema_format: str | None = None) -> Any:
    """Cast a string value to a target JSON schema type.

    Args:
        value: The string value to cast
        schema_type: The JSON schema type (e.g., "string", "integer", "number", "boolean")
        schema_format: Optional format specifier (e.g., "date-time")

    Returns:
        The casted value, or the original string if casting fails
    """
    if schema_type == "string":
        return value

    if schema_type == "integer":
        try:
            return int(value)
        except (ValueError, TypeError):
            logger.debug(f"Failed to cast '{value}' to integer, keeping as string")
            return value

    if schema_type == "number":
        try:
            return float(value)
        except (ValueError, TypeError):
            logger.debug(f"Failed to cast '{value}' to number, keeping as string")
            return value

    if schema_type == "boolean":
        value_lower = value.lower().strip()
        if value_lower in ("true", "1", "yes"):
            return True
        if value_lower in ("false", "0", "no"):
            return False
        logger.debug(f"Failed to cast '{value}' to boolean, keeping as string")
        return value

    if schema_type == "array":
        if value.strip().startswith("["):
            try:
                result = json.loads(value)
                if isinstance(result, list):
                    return result
            except (json.JSONDecodeError, TypeError):
                pass
        logger.debug(f"Failed to cast '{value}' to array, keeping as string")
        return value

    if schema_type == "object":
        if value.strip().startswith("{"):
            try:
                result = json.loads(value)
                if isinstance(result, dict):
                    return result
            except (json.JSONDecodeError, TypeError):
                pass
        logger.debug(f"Failed to cast '{value}' to object, keeping as string")
        return value

    return value


def _get_schema_for_path(spec: dict[str, Any] | None, path: str) -> tuple[str | None, str | None]:
    """Extract type information for a given dot-notation path from the spec.

    Args:
        spec: The connector spec dictionary
        path: Dot-notation path (e.g., "credentials.password", "api_key")

    Returns:
        Tuple of (type, format) where both can be None if not found
    """
    if not spec:
        return None, None

    try:
        connection_spec = spec.get("connection_specification", {})
        properties = connection_spec.get("properties", {})

        if not properties:
            return None, None

        path_parts = path.split(".")
        current_properties = properties

        for i, part in enumerate(path_parts):
            if part not in current_properties:
                return None, None

            field_schema = current_properties[part]

            if i == len(path_parts) - 1:
                schema_type = field_schema.get("type")
                schema_format = field_schema.get("format")
                return schema_type, schema_format

            if field_schema.get("type") == "object":
                current_properties = field_schema.get("properties", {})
            else:
                return None, None

        return None, None

    except Exception as e:
        logger.debug(f"Error extracting schema for path '{path}': {e}")
        return None, None


def _cast_secrets_to_types(secrets: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    """Cast secret values to appropriate types based on the spec.

    Recursively traverses the secrets dictionary and casts string values
    to their target types as defined in the spec.

    Args:
        secrets: Nested dictionary of secrets to cast
        spec: Connector spec dictionary containing type information

    Returns:
        New dictionary with values cast to appropriate types
    """

    def _cast_recursive(obj: Any, path_prefix: str = "") -> Any:
        """Recursively cast values in nested structures."""
        if isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                current_path = f"{path_prefix}.{key}" if path_prefix else key
                result[key] = _cast_recursive(value, current_path)
            return result
        elif isinstance(obj, str):
            # Only cast string values
            schema_type, schema_format = _get_schema_for_path(spec, path_prefix)
            if schema_type:
                return _cast_value_to_type(obj, schema_type, schema_format)
            return obj
        else:
            # Non-string, non-dict values pass through unchanged
            return obj

    return cast(dict[str, Any], _cast_recursive(secrets))


def hydrate_config(
    config: dict[str, Any],
    dotenv_file_uris: str | list[str] | None = None,
    *,
    spec: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Hydrate configuration with secrets from dotenv files and privatebin URLs using dot notation.

    Dotenv keys are mapped directly to config paths using dot notation:
    - credentials.password=foo   -> {"credentials": {"password": "foo"}}
    - api_key=value              -> {"api_key": "value"}
    - oauth.client_secret=value  -> {"oauth": {"client_secret": "value"}}

    If a spec is provided, secret values will be cast to the types specified in the
    connection_specification. Values that cannot be cast will remain as strings.

    Args:
        config: Configuration dictionary to hydrate with secrets
        dotenv_file_uris: List of paths/URLs to .env files or privatebin URLs,
                              or comma-separated string, or single string
        spec: Connector spec dictionary to use for type casting (keyword-only)

    Returns:
        Configuration with secrets injected from .env files and privatebin URLs
    """
    config = config or {}
    if not isinstance(config, dict):
        raise TypeError(f"Expected config to be a dictionary, got {type(config)}")

    if not dotenv_file_uris:
        return config

    secrets = _load_secrets(dotenv_file_uris)
    if not secrets:
        return config

    # Cast secrets to appropriate types if spec is provided
    if spec:
        typed_secrets = _cast_secrets_to_types(secrets, spec)
    else:
        typed_secrets = secrets

    return _merge_nested_dicts(config, typed_secrets)


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

    all_secrets = _load_secrets(dotenv_path)
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
            description="Absolute path to the .env file to add secrets to, or privatebin URL to check."
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
    *,
    allow_create: Annotated[
        bool,
        Field(description="Create the file if it doesn't exist"),
    ] = True,
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
    validation_errors = _validate_secrets_uris(dotenv_path)
    if validation_errors:
        return f"Validation failed: {'; '.join(validation_errors)}"

    if _is_privatebin_url(dotenv_path):
        config_paths_list = config_paths.split(",") if config_paths else []
        if not any([manifest, config_paths_list]):
            return "Error: Must provide either manifest or config_paths"

        secrets_to_add = []

        if manifest:
            manifest_dict, _ = parse_manifest_input(manifest)
            secrets_to_add.extend(_extract_secrets_names_from_manifest(manifest_dict))

        if config_paths_list:
            for path in config_paths_list:
                dotenv_key = _config_path_to_dotenv_key(path)
                secrets_to_add.append(dotenv_key)

        if not secrets_to_add:
            return "No secrets found to add"

        existing_secrets = _load_secrets(dotenv_path)

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
            manifest_dict, _ = parse_manifest_input(manifest)
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
