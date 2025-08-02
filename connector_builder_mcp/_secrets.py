"""Secrets management for connector configurations using dotenv files.

This module provides stateless tools for managing secrets in .env files without
exposing actual secret values to the LLM. All functions require explicit dotenv
file paths to be passed by the caller.
"""

import logging
from pathlib import Path
from typing import Annotated, Any

from dotenv import dotenv_values, set_key
from fastmcp import FastMCP
from pydantic import BaseModel, Field

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


def set_dotenv_path(
    file_path: Annotated[str, Field(description="Path to the .env file to use for secrets")],
) -> str:
    """Set up a dotenv file for secrets management.

    This creates the file and directory structure if they don't exist.

    Args:
        file_path: Path to the .env file to create/use

    Returns:
        Confirmation message with the absolute path
    """
    abs_path = str(Path(file_path).resolve())
    logger.info(f"Setting up dotenv file at: {abs_path}")

    Path(abs_path).parent.mkdir(parents=True, exist_ok=True)
    Path(abs_path).touch()

    return f"Dotenv file ready at: {abs_path}"


def load_secrets(dotenv_path: str) -> dict[str, str]:
    """Load secrets from the specified dotenv file.

    Args:
        dotenv_path: Path to the .env file to load secrets from

    Returns:
        Dictionary of secret key-value pairs
    """
    if not Path(dotenv_path).exists():
        logger.warning(f"Secrets file not found: {dotenv_path}")
        return {}

    try:
        secrets = dotenv_values(dotenv_path)
        filtered_secrets = {k: v for k, v in (secrets or {}).items() if v is not None}
        logger.info(f"Loaded {len(filtered_secrets)} secrets from {dotenv_path}")
        return filtered_secrets
    except Exception as e:
        logger.error(f"Error loading secrets from {dotenv_path}: {e}")
        return {}


def hydrate_config(config: dict[str, Any], dotenv_path: str | None = None) -> dict[str, Any]:
    """Hydrate configuration with secrets from dotenv file using naming convention.

    Environment variables are mapped to config paths using underscore convention:
    - CREDENTIALS_PASSWORD -> credentials.password
    - API_KEY -> api_key
    - OAUTH_CLIENT_SECRET -> oauth.client_secret

    Args:
        config: Configuration dictionary to hydrate with secrets
        dotenv_path: Path to the .env file to load secrets from. If None, returns config unchanged.

    Returns:
        Configuration with secrets injected from .env file
    """
    if not config or not dotenv_path:
        return config

    secrets = load_secrets(dotenv_path)
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

    def _env_var_to_path(env_var: str) -> list[str]:
        """Convert environment variable name to config path.

        Examples:
        - CREDENTIALS_PASSWORD -> ['credentials', 'password']
        - API_KEY -> ['api_key']
        - OAUTH_CLIENT_SECRET -> ['oauth', 'client_secret']
        """
        lower_name = env_var.lower()

        if env_var in ["API_KEY", "ACCESS_TOKEN", "CLIENT_ID", "CLIENT_SECRET", "REFRESH_TOKEN"]:
            return [lower_name]

        parts = lower_name.split("_")

        # For single part, return as-is
        if len(parts) == 1:
            return parts

        # For two parts, check if it should be nested or flat
        if len(parts) == 2:
            if parts[0] in ["credentials", "oauth", "auth", "config", "settings"]:
                return parts
            else:
                return [lower_name]

        # For multi-part names, use first part as parent and join rest
        return [parts[0], "_".join(parts[1:])]

    result = config.copy()

    for env_var, secret_value in secrets.items():
        if secret_value and not secret_value.startswith("#"):
            path = _env_var_to_path(env_var)
            _set_nested_value(result, path, secret_value)

    return result


def list_dotenv_secrets(
    dotenv_path: Annotated[str, Field(description="Path to the .env file to list secrets from")],
) -> SecretsFileInfo:
    """List all secrets in the specified dotenv file without exposing values.

    Args:
        dotenv_path: Path to the .env file to list secrets from

    Returns:
        Information about the secrets file and its contents
    """
    file_path = Path(dotenv_path)

    secrets_info = []
    if file_path.exists():
        try:
            secrets = dotenv_values(dotenv_path)
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


def populate_dotenv_missing_secrets_stubs(
    dotenv_path: Annotated[str, Field(description="Path to the .env file to add secrets to")],
    manifest: Annotated[
        dict[str, Any] | None, Field(description="Connector manifest to analyze for secrets")
    ] = None,
    config_paths: Annotated[
        list[str] | None,
        Field(
            description="List of config paths like ['credentials.password', 'oauth.client_secret']"
        ),
    ] = None,
    allow_create: Annotated[bool, Field(description="Create the file if it doesn't exist")] = True,
) -> str:
    """Add secret stubs to the specified dotenv file for the user to fill in.

    Supports two modes:
    1. Manifest-based: Pass manifest to auto-detect secrets from connection_specification
    2. Path-based: Pass config_paths list like ['credentials.password', 'oauth.client_secret']

    Args:
        dotenv_path: Path to the .env file to add secrets to
        manifest: Connector manifest to analyze for airbyte_secret fields
        config_paths: List of config paths to convert to environment variables
        allow_create: Create the file if it doesn't exist

    Returns:
        Message about the operation result
    """
    if not any([manifest, config_paths]):
        return "Error: Must provide either manifest or config_paths"

    try:
        if allow_create:
            Path(dotenv_path).parent.mkdir(parents=True, exist_ok=True)
            Path(dotenv_path).touch()
        elif not Path(dotenv_path).exists():
            return f"Error: File {dotenv_path} does not exist and allow_create=False"

        secrets_to_add = []

        if manifest:
            secrets_to_add.extend(_extract_secrets_names_from_manifest(manifest))

        if config_paths:
            for path in config_paths:
                env_var = _config_path_to_env_var(path)
                secrets_to_add.append(env_var)

        if not secrets_to_add:
            return "No secrets found to add"

        added_count = 0
        for env_var in secrets_to_add:
            placeholder_value = f"# TODO: Set actual value for {env_var}"
            set_key(dotenv_path, env_var, placeholder_value)
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
        List of environment variable names
    """
    secrets = []

    try:
        spec = manifest.get("spec", {})
        connection_spec = spec.get("connection_specification", {})
        properties = connection_spec.get("properties", {})

        for field_name, field_spec in properties.items():
            if field_spec.get("airbyte_secret", False):
                env_var = _config_path_to_env_var(field_name)
                secrets.append(env_var)

    except Exception as e:
        logger.warning(f"Error extracting secrets from manifest: {e}")

    return secrets


def _config_path_to_env_var(config_path: str) -> str:
    """Convert config path to environment variable name.

    Examples:
    - 'credentials.password' -> 'CREDENTIALS_PASSWORD'
    - 'api_key' -> 'API_KEY'
    - 'oauth.client_secret' -> 'OAUTH_CLIENT_SECRET'

    Args:
        config_path: Dot-separated config path

    Returns:
        Environment variable name
    """
    return config_path.replace(".", "_").upper()


def get_dotenv_path(
    dotenv_path: Annotated[
        str, Field(description="Path to the .env file to get absolute path for")
    ],
) -> str:
    """Get the absolute path to the specified dotenv file for user reference.

    Args:
        dotenv_path: Path to the .env file

    Returns:
        Absolute path to the dotenv file
    """
    return str(Path(dotenv_path).absolute())


def register_secrets_tools(app: FastMCP) -> None:
    """Register secrets management tools with the FastMCP app.

    Args:
        app: FastMCP application instance
    """
    app.tool(set_dotenv_path)
    app.tool(list_dotenv_secrets)
    app.tool(populate_dotenv_missing_secrets_stubs)
    app.tool(get_dotenv_path)
