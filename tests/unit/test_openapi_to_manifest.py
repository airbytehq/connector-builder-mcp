"""Unit tests for OpenAPI to Airbyte manifest conversion."""

import pytest
import yaml

from connector_builder_mcp.build_strategies.declarative_openapi_v3.openapi_to_manifest import (
    build_connection_spec,
    build_manifest,
    detect_auth_scheme,
    detect_base_url,
    enumerate_candidate_streams,
    generate_manifest_from_openapi,
    infer_paginator,
    infer_record_selector,
    parse_openapi_spec,
)


def test_parse_openapi_spec_yaml():
    """Test parsing a YAML OpenAPI spec."""
    spec_yaml = """
openapi: 3.0.0
info:
  title: Test API
  version: 1.0.0
paths:
  /users:
    get:
      summary: List users
"""
    spec = parse_openapi_spec(spec_yaml)
    assert spec["openapi"] == "3.0.0"
    assert spec["info"]["title"] == "Test API"
    assert "/users" in spec["paths"]


def test_parse_openapi_spec_json():
    """Test parsing a JSON OpenAPI spec."""
    spec_json = '{"openapi": "3.0.0", "info": {"title": "Test API", "version": "1.0.0"}, "paths": {}}'
    spec = parse_openapi_spec(spec_json)
    assert spec["openapi"] == "3.0.0"
    assert spec["info"]["title"] == "Test API"


def test_parse_openapi_spec_invalid():
    """Test parsing an invalid OpenAPI spec."""
    with pytest.raises(ValueError, match="Failed to parse OpenAPI spec"):
        parse_openapi_spec("not valid yaml or json {{{")


def test_detect_base_url_single_server():
    """Test detecting base URL from a single server."""
    spec = {
        "servers": [
            {"url": "https://api.example.com/v1"}
        ]
    }
    base_url = detect_base_url(spec)
    assert base_url == "https://api.example.com/v1"


def test_detect_base_url_multiple_servers():
    """Test detecting base URL from multiple servers."""
    spec = {
        "servers": [
            {"url": "https://api.example.com/v1"},
            {"url": "https://api-staging.example.com/v1"}
        ]
    }
    base_url = detect_base_url(spec)
    assert base_url is None


def test_detect_base_url_no_servers():
    """Test detecting base URL when no servers are defined."""
    spec = {}
    base_url = detect_base_url(spec)
    assert base_url is None


@pytest.mark.parametrize(
    "security_schemes,expected_type,expected_fields",
    [
        (
            {
                "ApiKeyAuth": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-API-Key"
                }
            },
            "ApiKeyAuthenticator",
            ["api_key"]
        ),
        (
            {
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer"
                }
            },
            "BearerAuthenticator",
            ["api_token"]
        ),
        (
            {
                "BasicAuth": {
                    "type": "http",
                    "scheme": "basic"
                }
            },
            "BasicHttpAuthenticator",
            ["username", "password"]
        ),
        (
            {},
            "NoAuth",
            []
        ),
    ]
)
def test_detect_auth_scheme(security_schemes, expected_type, expected_fields):
    """Test detecting authentication schemes."""
    spec = {
        "components": {
            "securitySchemes": security_schemes
        }
    }
    if security_schemes:
        spec["security"] = [{list(security_schemes.keys())[0]: []}]
    
    auth_config = detect_auth_scheme(spec)
    assert auth_config["type"] == expected_type
    assert set(auth_config["connection_spec_fields"]) == set(expected_fields)


def test_infer_record_selector_with_hint():
    """Test inferring record selector with x-airbyte hint."""
    response_schema = {}
    x_airbyte_hints = {"record-selector": "$.results"}
    
    selector = infer_record_selector(response_schema, x_airbyte_hints)
    assert selector == "$.results"


def test_infer_record_selector_array_response():
    """Test inferring record selector for array response."""
    response_schema = {
        "type": "array",
        "items": {"type": "object"}
    }
    
    selector = infer_record_selector(response_schema, {})
    assert selector == "$"


def test_infer_record_selector_object_with_data_field():
    """Test inferring record selector for object with data field."""
    response_schema = {
        "type": "object",
        "properties": {
            "data": {
                "type": "array",
                "items": {"type": "object"}
            }
        }
    }
    
    selector = infer_record_selector(response_schema, {})
    assert selector == "$.data"


def test_infer_record_selector_object_with_results_field():
    """Test inferring record selector for object with results field."""
    response_schema = {
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "items": {"type": "object"}
            }
        }
    }
    
    selector = infer_record_selector(response_schema, {})
    assert selector == "$.results"


def test_infer_paginator_with_hint():
    """Test inferring paginator with x-airbyte hint."""
    operation = {}
    response_schema = {}
    x_airbyte_hints = {
        "pagination": {
            "type": "offset",
            "limit_param": "limit",
            "offset_param": "offset"
        }
    }
    
    paginator = infer_paginator(operation, response_schema, x_airbyte_hints)
    assert paginator["type"] == "DefaultPaginator"
    assert paginator["pagination_strategy"]["type"] == "OffsetIncrement"


def test_infer_paginator_offset_limit():
    """Test inferring offset/limit paginator from parameters."""
    operation = {
        "parameters": [
            {"name": "offset", "in": "query"},
            {"name": "limit", "in": "query"}
        ]
    }
    response_schema = {}
    
    paginator = infer_paginator(operation, response_schema, {})
    assert paginator["type"] == "DefaultPaginator"
    assert paginator["pagination_strategy"]["type"] == "OffsetIncrement"


def test_infer_paginator_page_page_size():
    """Test inferring page/page_size paginator from parameters."""
    operation = {
        "parameters": [
            {"name": "page", "in": "query"},
            {"name": "page_size", "in": "query"}
        ]
    }
    response_schema = {}
    
    paginator = infer_paginator(operation, response_schema, {})
    assert paginator["type"] == "DefaultPaginator"
    assert paginator["pagination_strategy"]["type"] == "PageIncrement"


def test_infer_paginator_cursor():
    """Test inferring cursor paginator from response schema."""
    operation = {}
    response_schema = {
        "type": "object",
        "properties": {
            "next_cursor": {"type": "string"}
        }
    }
    
    paginator = infer_paginator(operation, response_schema, {})
    assert paginator["type"] == "DefaultPaginator"
    assert paginator["pagination_strategy"]["type"] == "CursorPagination"


def test_infer_paginator_no_pagination():
    """Test when no pagination is detected."""
    operation = {}
    response_schema = {}
    
    paginator = infer_paginator(operation, response_schema, {})
    assert paginator is None


def test_enumerate_candidate_streams():
    """Test enumerating candidate streams from OpenAPI spec."""
    spec = {
        "paths": {
            "/users": {
                "get": {
                    "operationId": "listUsers",
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {"type": "object"}
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "/users/{id}": {
                "get": {
                    "operationId": "getUser",
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {"type": "object"}
                                }
                            }
                        }
                    }
                }
            },
            "/posts": {
                "post": {
                    "operationId": "createPost"
                }
            }
        }
    }
    
    streams = enumerate_candidate_streams(spec)
    assert len(streams) == 1
    assert streams[0]["name"] == "users"
    assert streams[0]["path"] == "/users"


def test_build_connection_spec_with_auth():
    """Test building connection spec with authentication."""
    spec = {"info": {"title": "Test API"}}
    auth_config = {
        "type": "ApiKeyAuthenticator",
        "connection_spec_fields": ["api_key"]
    }
    base_url = None
    
    conn_spec = build_connection_spec(spec, auth_config, base_url)
    assert conn_spec["type"] == "object"
    assert "api_key" in conn_spec["properties"]
    assert conn_spec["properties"]["api_key"]["type"] == "string"
    assert conn_spec["properties"]["api_key"]["airbyte_secret"] is True


def test_build_connection_spec_with_base_url():
    """Test building connection spec with base URL."""
    spec = {"info": {"title": "Test API"}}
    auth_config = {
        "type": "NoAuth",
        "connection_spec_fields": []
    }
    base_url = None
    
    conn_spec = build_connection_spec(spec, auth_config, base_url)
    assert "base_url" in conn_spec["properties"]


def test_build_manifest():
    """Test building a complete manifest."""
    source_name = "test_source"
    spec = {
        "info": {"title": "Test API", "version": "1.0.0"},
        "servers": [{"url": "https://api.example.com"}]
    }
    streams = [
        {
            "name": "users",
            "path": "/users",
            "primary_key": None,
            "schema": {"type": "array"},
            "retriever": {
                "type": "SimpleRetriever",
                "requester": {
                    "type": "HttpRequester",
                    "url_base": "https://api.example.com",
                    "path": "/users",
                    "http_method": "GET"
                },
                "record_selector": {
                    "type": "RecordSelector",
                    "extractor": {
                        "type": "DpathExtractor",
                        "field_path": ["$"]
                    }
                }
            }
        }
    ]
    auth_config = {
        "type": "NoAuth",
        "connection_spec_fields": []
    }
    base_url = "https://api.example.com"
    
    manifest = build_manifest(source_name, spec, streams, auth_config, base_url)
    
    assert manifest["version"] == "6.51.0"
    assert manifest["type"] == "DeclarativeSource"
    assert manifest["metadata"]["name"] == source_name
    assert len(manifest["streams"]) == 1
    assert manifest["streams"][0]["name"] == "users"


def test_generate_manifest_from_openapi_simple():
    """Test generating manifest from a simple OpenAPI spec."""
    spec_yaml = """
openapi: 3.0.0
info:
  title: Test API
  version: 1.0.0
servers:
  - url: https://api.example.com/v1
paths:
  /users:
    get:
      operationId: listUsers
      responses:
        '200':
          description: List of users
          content:
            application/json:
              schema:
                type: array
                items:
                  type: object
                  properties:
                    id:
                      type: integer
                    name:
                      type: string
"""
    
    manifest_yaml, warnings = generate_manifest_from_openapi(
        spec_content=spec_yaml,
        source_name="test_source"
    )
    
    assert isinstance(manifest_yaml, str)
    assert isinstance(warnings, list)
    
    manifest = yaml.safe_load(manifest_yaml)
    assert manifest["version"] == "6.51.0"
    assert manifest["type"] == "DeclarativeSource"
    assert len(manifest["streams"]) == 1
    assert manifest["streams"][0]["name"] == "users"


def test_generate_manifest_from_openapi_with_auth():
    """Test generating manifest from OpenAPI spec with authentication."""
    spec_yaml = """
openapi: 3.0.0
info:
  title: Test API
  version: 1.0.0
servers:
  - url: https://api.example.com/v1
components:
  securitySchemes:
    ApiKeyAuth:
      type: apiKey
      in: header
      name: X-API-Key
security:
  - ApiKeyAuth: []
paths:
  /users:
    get:
      operationId: listUsers
      responses:
        '200':
          description: List of users
          content:
            application/json:
              schema:
                type: object
                properties:
                  data:
                    type: array
                    items:
                      type: object
"""
    
    manifest_yaml, warnings = generate_manifest_from_openapi(
        spec_content=spec_yaml,
        source_name="test_source"
    )
    
    manifest = yaml.safe_load(manifest_yaml)
    assert manifest["definitions"]["base_requester"]["authenticator"]["type"] == "ApiKeyAuthenticator"
    assert "api_key" in manifest["spec"]["connection_specification"]["properties"]


def test_generate_manifest_from_openapi_with_pagination():
    """Test generating manifest from OpenAPI spec with pagination."""
    spec_yaml = """
openapi: 3.0.0
info:
  title: Test API
  version: 1.0.0
servers:
  - url: https://api.example.com/v1
paths:
  /users:
    get:
      operationId: listUsers
      parameters:
        - name: offset
          in: query
          schema:
            type: integer
        - name: limit
          in: query
          schema:
            type: integer
      responses:
        '200':
          description: List of users
          content:
            application/json:
              schema:
                type: array
                items:
                  type: object
"""
    
    manifest_yaml, warnings = generate_manifest_from_openapi(
        spec_content=spec_yaml,
        source_name="test_source"
    )
    
    manifest = yaml.safe_load(manifest_yaml)
    stream = manifest["streams"][0]
    assert "paginator" in stream["retriever"]
    assert stream["retriever"]["paginator"]["pagination_strategy"]["type"] == "OffsetIncrement"


def test_generate_manifest_from_openapi_no_streams():
    """Test generating manifest from OpenAPI spec with no valid streams."""
    spec_yaml = """
openapi: 3.0.0
info:
  title: Test API
  version: 1.0.0
paths:
  /users/{id}:
    get:
      operationId: getUser
      responses:
        '200':
          description: Single user
          content:
            application/json:
              schema:
                type: object
"""
    
    with pytest.raises(ValueError, match="No candidate streams found"):
        generate_manifest_from_openapi(
            spec_content=spec_yaml,
            source_name="test_source"
        )
