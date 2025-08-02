"""Secrets management for connector configurations using dotenv files.

This module provides tools for managing secrets in .env files without exposing
actual secret values to the LLM. It uses a file path approach where the LLM can
manage secret stubs and the user provides actual values.
"""

import logging
import os
from pathlib import Path
from typing import Annotated, Any

from dotenv import dotenv_values, set_key
from fastmcp import FastMCP
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

SECRETS_FILE_ENV_VAR = "CONNECTOR_BUILDER_SECRETS_FILE"
DEFAULT_SECRETS_FILE = ".env"

_current_dotenv_path: str | None = None


class SecretInfo(BaseModel):
    """Information about a secret without exposing its value."""

    key: str
    is_set: bool
    description: str = ""


class SecretsFileInfo(BaseModel):
    """Information about the secrets file and its contents."""

    file_path: str
    exists: bool
    secrets: list[SecretInfo]


def get_secrets_file_path() -> str:
    """Get the path to the secrets file from tool setting, environment, or default.

    Priority order:
    1. Path set via set_dotenv_path tool
    2. Environment variable CONNECTOR_BUILDER_SECRETS_FILE
    3. Default .env file
    """
    if _current_dotenv_path:
        return _current_dotenv_path
    return os.environ.get(SECRETS_FILE_ENV_VAR, DEFAULT_SECRETS_FILE)


def set_dotenv_path(
    file_path: Annotated[str, Field(description="Path to the .env file to use for secrets")]
) -> str:
    """Set the path to the dotenv file for secrets management.

    This allows users to easily switch between different configuration files.

    Args:
        file_path: Path to the .env file to use

    Returns:
        Confirmation message with the absolute path
    """
    global _current_dotenv_path

    abs_path = str(Path(file_path).resolve())
    _current_dotenv_path = abs_path

    logger.info(f"Set dotenv path to: {abs_path}")

    Path(abs_path).parent.mkdir(parents=True, exist_ok=True)
    Path(abs_path).touch()

    return f"Dotenv path set to: {abs_path}"


def load_secrets() -> dict[str, str]:
    """Load secrets from the dotenv file.

    Returns:
        Dictionary of secret key-value pairs
    """
    secrets_file = get_secrets_file_path()
    if not Path(secrets_file).exists():
        logger.warning(f"Secrets file not found: {secrets_file}")
        return {}

    try:
        secrets = dotenv_values(secrets_file)
        filtered_secrets = {k: v for k, v in (secrets or {}).items() if v is not None}
        logger.info(f"Loaded {len(filtered_secrets)} secrets from {secrets_file}")
        return filtered_secrets
    except Exception as e:
        logger.error(f"Error loading secrets from {secrets_file}: {e}")
        return {}


def hydrate_config(config: dict[str, Any]) -> dict[str, Any]:
    """Hydrate configuration with secrets from dotenv file using naming convention.

    Environment variables are mapped to config paths using underscore convention:
    - CREDENTIALS_PASSWORD -> credentials.password
    - API_KEY -> api_key
    - OAUTH_CLIENT_SECRET -> oauth.client_secret

    Args:
        config: Configuration dictionary to hydrate with secrets

    Returns:
        Configuration with secrets injected from .env file
    """
    if not config:
        return config

    secrets = load_secrets()
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

        if env_var in ['API_KEY', 'ACCESS_TOKEN', 'CLIENT_ID', 'CLIENT_SECRET', 'REFRESH_TOKEN']:
            return [lower_name]

        parts = lower_name.split('_')

        # For single part, return as-is
        if len(parts) == 1:
            return parts

        # For two parts, check if it should be nested or flat
        if len(parts) == 2:
            if parts[0] in ['credentials', 'oauth', 'auth', 'config', 'settings']:
                return parts
            else:
                return [lower_name]

        # For multi-part names, use first part as parent and join rest
        return [parts[0], '_'.join(parts[1:])]

    result = config.copy()

    for env_var, secret_value in secrets.items():
        if secret_value and not secret_value.startswith('#'):
            path = _env_var_to_path(env_var)
            _set_nested_value(result, path, secret_value)

    return result


def list_secrets() -> SecretsFileInfo:
    """List all secrets in the secrets file without exposing values.

    Returns:
        Information about the secrets file and its contents
    """
    secrets_file = get_secrets_file_path()
    file_path = Path(secrets_file)

    secrets_info = []
    if file_path.exists():
        try:
            secrets = dotenv_values(secrets_file)
            for key, value in (secrets or {}).items():
                secrets_info.append(SecretInfo(
                    key=key,
                    is_set=bool(value and value.strip()),
                    description=f"Secret value for {key}"
                ))
        except Exception as e:
            logger.error(f"Error reading secrets file: {e}")

    return SecretsFileInfo(
        file_path=str(file_path.absolute()),
        exists=file_path.exists(),
        secrets=secrets_info
    )


def add_secret_stub(
    secret_key: Annotated[str, Field(description="Name of the secret to add")],
    description: Annotated[str, Field(description="Description of what this secret is for")] = "",
) -> str:
    """Add a secret stub to the secrets file for the user to fill in.

    Args:
        secret_key: Name of the secret to add
        description: Optional description of the secret

    Returns:
        Message about the operation result
    """
    secrets_file = get_secrets_file_path()

    try:
        Path(secrets_file).touch()

        placeholder_value = f"# TODO: Set actual value for {secret_key}"
        if description:
            placeholder_value += f" - {description}"

        set_key(secrets_file, secret_key, placeholder_value)

        return f"Added secret stub '{secret_key}' to {secrets_file}. Please set the actual value."

    except Exception as e:
        logger.error(f"Error adding secret stub: {e}")
        return f"Error adding secret stub: {str(e)}"


def get_secrets_file_path_for_user() -> str:
    """Get the absolute path to the secrets file for user reference.

    Returns:
        Absolute path to the secrets file
    """
    secrets_file = get_secrets_file_path()
    return str(Path(secrets_file).absolute())


def register_secrets_tools(app: FastMCP) -> None:
    """Register secrets management tools with the FastMCP app.

    Args:
        app: FastMCP application instance
    """
    app.tool(set_dotenv_path)
    app.tool(list_secrets)
    app.tool(add_secret_stub)
    app.tool(get_secrets_file_path_for_user)
