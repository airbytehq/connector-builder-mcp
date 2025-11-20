"""OpenAPI to Airbyte Declarative Manifest Converter.

This module provides functions to convert OpenAPI 3.0 specifications into
Airbyte declarative connector manifests.
"""

from __future__ import annotations

import logging
from typing import Any

import yaml


logger = logging.getLogger(__name__)


def parse_openapi_spec(spec_content: str) -> dict[str, Any]:
    """Parse OpenAPI specification from YAML or JSON string.

    Args:
        spec_content: OpenAPI specification as YAML or JSON string

    Returns:
        Parsed OpenAPI specification as dictionary

    Raises:
        ValueError: If spec cannot be parsed
    """
    try:
        spec = yaml.safe_load(spec_content)
        if not isinstance(spec, dict):
            raise ValueError("OpenAPI spec must be a dictionary")
        return spec
    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse OpenAPI spec: {e}") from e


def detect_base_url(spec: dict[str, Any]) -> str | None:
    """Detect base URL from OpenAPI servers section.

    Args:
        spec: Parsed OpenAPI specification

    Returns:
        Base URL or None if not found
    """
    servers = spec.get("servers", [])
    if servers and isinstance(servers, list) and len(servers) > 0:
        first_server = servers[0]
        if isinstance(first_server, dict) and "url" in first_server:
            return first_server["url"]
    return None


def detect_auth_scheme(spec: dict[str, Any]) -> dict[str, Any]:
    """Detect authentication scheme from OpenAPI security schemes.

    Args:
        spec: Parsed OpenAPI specification

    Returns:
        Dictionary with 'type' and 'config' for Airbyte authenticator
    """
    components = spec.get("components", {})
    security_schemes = components.get("securitySchemes", {})

    for _scheme_name, scheme_def in security_schemes.items():
        if not isinstance(scheme_def, dict):
            continue

        scheme_type = scheme_def.get("type", "").lower()

        if scheme_type == "apikey":
            header_name = scheme_def.get("name", "X-API-Key")
            return {
                "type": "ApiKeyAuthenticator",
                "header": header_name,
                "api_token": "{{ config['api_key'] }}",
            }

        elif scheme_type == "http" and scheme_def.get("scheme", "").lower() == "bearer":
            return {
                "type": "BearerAuthenticator",
                "api_token": "{{ config['api_token'] }}",
            }

        elif scheme_type == "http" and scheme_def.get("scheme", "").lower() == "basic":
            return {
                "type": "BasicHttpAuthenticator",
                "username": "{{ config['username'] }}",
                "password": "{{ config['password'] }}",
            }

    return {
        "type": "NoAuth",
    }


def infer_record_selector(
    response_schema: dict[str, Any] | None,
    x_airbyte_hints: dict[str, Any] | None = None,
) -> str:
    """Infer the record selector path from response schema.

    Args:
        response_schema: OpenAPI response schema
        x_airbyte_hints: Optional x-airbyte-* extension hints

    Returns:
        JSONPath selector string (e.g., "$.data", "$.results")
    """
    if x_airbyte_hints and "record_selector" in x_airbyte_hints:
        return x_airbyte_hints["record_selector"]

    if response_schema and isinstance(response_schema, dict):
        properties = response_schema.get("properties", {})

        for field_name in ["data", "results", "items", "records", "list"]:
            if field_name in properties:
                field_schema = properties[field_name]
                if isinstance(field_schema, dict) and field_schema.get("type") == "array":
                    return f"$.{field_name}"

        if response_schema.get("type") == "array":
            return "$"

    return "$"


def infer_paginator(
    operation: dict[str, Any],
    response_schema: dict[str, Any] | None,
    x_airbyte_hints: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Infer pagination configuration from operation and response schema.

    Args:
        operation: OpenAPI operation definition
        response_schema: OpenAPI response schema
        x_airbyte_hints: Optional x-airbyte-* extension hints

    Returns:
        Paginator configuration or None if no pagination detected
    """
    if x_airbyte_hints and "pagination" in x_airbyte_hints:
        pagination_hint = x_airbyte_hints["pagination"]
        if pagination_hint.get("type") == "offset":
            return {
                "type": "DefaultPaginator",
                "pagination_strategy": {
                    "type": "OffsetIncrement",
                    "page_size": pagination_hint.get("page_size", 100),
                },
                "page_token_option": {
                    "type": "RequestOption",
                    "field_name": pagination_hint.get("offset_param", "offset"),
                    "inject_into": "request_parameter",
                },
            }
        elif pagination_hint.get("type") == "cursor":
            return {
                "type": "DefaultPaginator",
                "pagination_strategy": {
                    "type": "CursorPagination",
                    "cursor_value": pagination_hint.get(
                        "cursor_path", "{{ response.next_page_token }}"
                    ),
                    "stop_condition": pagination_hint.get(
                        "stop_condition", "{{ not response.next_page_token }}"
                    ),
                },
                "page_token_option": {
                    "type": "RequestOption",
                    "field_name": pagination_hint.get("cursor_param", "page_token"),
                    "inject_into": "request_parameter",
                },
            }

    parameters = operation.get("parameters", [])
    param_names = {p.get("name", "").lower() for p in parameters if isinstance(p, dict)}

    if "offset" in param_names and "limit" in param_names:
        return {
            "type": "DefaultPaginator",
            "pagination_strategy": {
                "type": "OffsetIncrement",
                "page_size": 100,
            },
            "page_token_option": {
                "type": "RequestOption",
                "field_name": "offset",
                "inject_into": "request_parameter",
            },
        }

    if "page" in param_names and ("page_size" in param_names or "per_page" in param_names):
        return {
            "type": "DefaultPaginator",
            "pagination_strategy": {
                "type": "PageIncrement",
                "start_from_page": 1,
                "page_size": 100,
            },
            "page_token_option": {
                "type": "RequestOption",
                "field_name": "page",
                "inject_into": "request_parameter",
            },
        }

    if response_schema and isinstance(response_schema, dict):
        properties = response_schema.get("properties", {})
        for cursor_field in ["next_page_token", "next", "cursor", "next_cursor"]:
            if cursor_field in properties:
                return {
                    "type": "DefaultPaginator",
                    "pagination_strategy": {
                        "type": "CursorPagination",
                        "cursor_value": f"{{{{ response.{cursor_field} }}}}",
                        "stop_condition": f"{{{{ not response.{cursor_field} }}}}",
                    },
                    "page_token_option": {
                        "type": "RequestOption",
                        "field_name": "page_token",
                        "inject_into": "request_parameter",
                    },
                }

    return None


def enumerate_candidate_streams(spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Enumerate candidate streams from OpenAPI paths.

    Only considers GET operations that appear to return lists/arrays.

    Args:
        spec: Parsed OpenAPI specification

    Returns:
        List of stream definitions with name, path, method, operation
    """
    streams = []
    paths = spec.get("paths", {})

    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue

        get_operation = path_item.get("get")
        if not get_operation or not isinstance(get_operation, dict):
            continue

        x_airbyte_resource = get_operation.get("x-airbyte-resource")

        stream_name = None
        if x_airbyte_resource:
            stream_name = x_airbyte_resource
        else:
            path_parts = [p for p in path.split("/") if p and not p.startswith("{")]
            if path_parts:
                stream_name = path_parts[-1]

        if not stream_name:
            continue

        responses = get_operation.get("responses", {})
        success_response = responses.get("200") or responses.get("201")
        response_schema = None

        if success_response and isinstance(success_response, dict):
            content = success_response.get("content", {})
            json_content = content.get("application/json", {})
            response_schema = json_content.get("schema")

        streams.append(
            {
                "name": stream_name,
                "path": path,
                "method": "GET",
                "operation": get_operation,
                "response_schema": response_schema,
            }
        )

    return streams


def build_connection_spec(
    spec: dict[str, Any],
    auth_config: dict[str, Any],
    base_url: str | None,
) -> dict[str, Any]:
    """Build connection specification for the connector.

    Args:
        spec: Parsed OpenAPI specification
        auth_config: Authentication configuration
        base_url: Base URL for the API

    Returns:
        Connection specification dictionary
    """
    properties: dict[str, Any] = {}
    required: list[str] = []

    if not base_url or len(spec.get("servers", [])) > 1:
        properties["base_url"] = {
            "type": "string",
            "title": "Base URL",
            "description": "The base URL for the API",
            "examples": [base_url] if base_url else [],
        }
        required.append("base_url")

    auth_type = auth_config.get("type")

    if auth_type == "ApiKeyAuthenticator":
        properties["api_key"] = {
            "type": "string",
            "title": "API Key",
            "description": "API key for authentication",
            "airbyte_secret": True,
        }
        required.append("api_key")

    elif auth_type == "BearerAuthenticator":
        properties["api_token"] = {
            "type": "string",
            "title": "API Token",
            "description": "Bearer token for authentication",
            "airbyte_secret": True,
        }
        required.append("api_token")

    elif auth_type == "BasicHttpAuthenticator":
        properties["username"] = {
            "type": "string",
            "title": "Username",
            "description": "Username for basic authentication",
        }
        properties["password"] = {
            "type": "string",
            "title": "Password",
            "description": "Password for basic authentication",
            "airbyte_secret": True,
        }
        required.extend(["username", "password"])

    return {
        "type": "object",
        "required": required,
        "properties": properties,
        "additionalProperties": True,
    }


def build_manifest(
    source_name: str,
    spec: dict[str, Any],
    streams: list[dict[str, Any]],
    auth_config: dict[str, Any],
    base_url: str | None,
) -> dict[str, Any]:
    """Build complete Airbyte declarative manifest.

    Args:
        source_name: Name of the source connector
        spec: Parsed OpenAPI specification
        streams: List of stream definitions
        auth_config: Authentication configuration
        base_url: Base URL for the API

    Returns:
        Complete Airbyte declarative manifest
    """
    connection_spec = build_connection_spec(spec, auth_config, base_url)

    stream_definitions = []

    for stream in streams:
        stream_name = stream["name"]
        path = stream["path"]
        operation = stream["operation"]
        response_schema = stream["response_schema"]

        x_airbyte_hints = {
            k.replace("x-airbyte-", ""): v
            for k, v in operation.items()
            if k.startswith("x-airbyte-")
        }

        record_selector = infer_record_selector(response_schema, x_airbyte_hints)

        paginator = infer_paginator(operation, response_schema, x_airbyte_hints)

        retriever: dict[str, Any] = {
            "type": "SimpleRetriever",
            "requester": {
                "type": "HttpRequester",
                "url_base": base_url or "{{ config['base_url'] }}",
                "path": path,
                "http_method": "GET",
                "authenticator": auth_config,
            },
            "record_selector": {
                "type": "RecordSelector",
                "extractor": {
                    "type": "DpathExtractor",
                    "field_path": [record_selector.lstrip("$.")],
                },
            },
        }

        if paginator:
            retriever["paginator"] = paginator
        else:
            retriever["paginator"] = {
                "type": "NoPagination",
            }

        stream_def = {
            "type": "DeclarativeStream",
            "name": stream_name,
            "primary_key": [],
            "retriever": retriever,
        }

        stream_definitions.append(stream_def)

    manifest = {
        "version": "0.79.0",
        "type": "DeclarativeSource",
        "check": {
            "type": "CheckStream",
            "stream_names": [streams[0]["name"]] if streams else [],
        },
        "streams": stream_definitions,
        "spec": {
            "type": "Spec",
            "connection_specification": connection_spec,
            "documentation_url": spec.get("info", {}).get("x-documentation-url", ""),
        },
    }

    return manifest


def generate_manifest_from_openapi(
    spec_content: str,
    source_name: str = "generated_source",
) -> tuple[str, list[str]]:
    """Generate Airbyte declarative manifest from OpenAPI specification.

    Args:
        spec_content: OpenAPI specification as YAML or JSON string
        source_name: Name for the generated source connector

    Returns:
        Tuple of (manifest_yaml_string, list_of_warnings)

    Raises:
        ValueError: If spec cannot be parsed or is invalid
    """
    warnings = []

    spec = parse_openapi_spec(spec_content)

    openapi_version = spec.get("openapi", "")
    if not openapi_version.startswith("3."):
        raise ValueError(f"Only OpenAPI 3.x is supported, got version: {openapi_version}")

    base_url = detect_base_url(spec)
    if not base_url:
        warnings.append("No base URL found in servers section. Will require base_url in config.")

    auth_config = detect_auth_scheme(spec)
    if auth_config.get("type") == "NoAuth":
        warnings.append("No authentication scheme detected. Connector will not authenticate.")

    streams = enumerate_candidate_streams(spec)
    if not streams:
        warnings.append(
            "No candidate streams found. Only GET operations returning lists are supported in MVP."
        )

    manifest = build_manifest(source_name, spec, streams, auth_config, base_url)

    manifest_yaml = yaml.dump(manifest, default_flow_style=False, sort_keys=False)

    return manifest_yaml, warnings
