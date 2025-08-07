"""Connector search functionality for finding manifest files with specific terms."""

from typing import TYPE_CHECKING, Any

import requests
import yaml
from pydantic import BaseModel, Field


if TYPE_CHECKING:
    from fastmcp import FastMCP


# Constants
HTTP_OK = 200
HTTP_UNAUTHORIZED = 401
MAX_DISPLAY_LENGTH = 50


class SchemaRetrievalError(Exception):
    """Custom exception for schema retrieval errors."""

    pass


class SearchConnectorManifestsRequest(BaseModel):
    """Request model for searching connector manifests."""
    search_terms: list[str] = Field(
        description="Array of strings that must all be present in the manifest.yaml file"
    )
    github_token: str | None = Field(
        default=None,
        description="GitHub token for authenticated requests (increases rate limits)"
    )


class ConnectorMatch(BaseModel):
    """Model for a connector that matches the search criteria."""
    name: str = Field(description="The connector name")
    repository: str = Field(description="GitHub repository")
    file_path: str = Field(description="Path to the manifest.yaml file")
    github_url: str = Field(description="GitHub URL to the manifest file")
    raw_url: str = Field(description="Raw content URL")
    match_locations: list[str] = Field(
        description="YAML paths where the search terms were found"
    )


class SearchConnectorManifestsResponse(BaseModel):
    """Response model for connector manifest search."""
    matching_connectors: list[ConnectorMatch] = Field(
        description="List of connectors that contain all search terms"
    )
    total_found: int = Field(
        description="Total number of manifest files found in search"
    )
    search_terms: list[str] = Field(
        description="The search terms that were used"
    )
    error_message: str | None = Field(
        default=None,
        description="Error message if search failed"
    )
    requires_auth: bool = Field(
        default=False,
        description="Whether the search requires GitHub authentication"
    )


class GetManifestSchemaResponse(BaseModel):
    """Response model for manifest JSON schema retrieval."""

    schema_yaml: str = Field(description="The manifest JSON schema in YAML format")
    schema_url: str = Field(description="URL where the schema was retrieved from")
    version: str = Field(description="Schema version if available")


def search_connector_manifests(
    request: SearchConnectorManifestsRequest,
) -> SearchConnectorManifestsResponse:
    """Search for connectors containing all specified strings in their manifest.yaml files.

    Uses GitHub code search API to efficiently find manifest files, then downloads
    and checks each one for ALL search terms (exact case, exact word matches).

    Args:
        request: Search request containing terms and optional GitHub token

    Returns:
        Response with matching connectors and search metadata

    Example:
        request = SearchConnectorManifestsRequest(
            search_terms=["HttpComponentsResolver", "stream_config"]
        )
        results = search_connector_manifests(request)
    """
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "connector-search-tool"
    }
    if request.github_token:
        headers["Authorization"] = f"token {request.github_token}"

    # Search GitHub for manifest.yaml files
    search_results, error_message, requires_auth = _search_github_manifests(
        headers, request.search_terms
    )

    # If we have an error, return it immediately
    if error_message:
        return SearchConnectorManifestsResponse(
            matching_connectors=[],
            total_found=0,
            search_terms=request.search_terms,
            error_message=error_message,
            requires_auth=requires_auth
        )

    # Process each result to check if ALL terms are present
    matching_connectors = []

    for result in search_results:
        match = _process_manifest_file(headers, result, request.search_terms)
        if match:
            matching_connectors.append(match)

    return SearchConnectorManifestsResponse(
        matching_connectors=matching_connectors,
        total_found=len(search_results),
        search_terms=request.search_terms
    )


def _search_github_manifests(
    headers: dict[str, str], search_terms: list[str]
) -> tuple[list[dict[str, Any]], str | None, bool]:
    """Search GitHub for manifest.yaml files that might contain our terms.

    Returns:
        tuple of (results, error_message, requires_auth)
    """
    # Build search query: filename:manifest.yaml + any of our search terms
    term_query = " OR ".join([f'"{term}"' for term in search_terms]) if search_terms else ""
    repo_filter = "repo:airbytehq/airbyte OR repo:airbytehq/airbyte-connectors"

    if term_query:
        query = f"filename:manifest.yaml AND ({repo_filter}) AND ({term_query})"
    else:
        query = f"filename:manifest.yaml AND ({repo_filter})"

    url = "https://api.github.com/search/code"
    params = {"q": query, "per_page": "100"}

    try:
        response = requests.get(url, params=params, headers=headers, timeout=30)
        if response.status_code == HTTP_OK:
            data = response.json()
            return list(data.get("items", [])), None, False
        if response.status_code == HTTP_UNAUTHORIZED:
            # Authentication required for GitHub code search API
            error_msg = (
                "GitHub authentication required for code search. "
                "Please provide a GitHub token to use this search functionality."
            )
            return [], error_msg, True

        error_msg = f"GitHub API error. Status: {response.status_code}"
        return [], error_msg, False
    except Exception as e:
        error_msg = f"Error searching GitHub manifests: {e}"
        return [], error_msg, False
def _process_manifest_file(
    headers: dict[str, str],
    result: dict[str, Any],
    search_terms: list[str]
) -> ConnectorMatch | None:
    """Download and check if manifest file contains ALL search terms."""
    try:
        # Download the file content
        response = requests.get(result["download_url"], headers=headers, timeout=30)
        if response.status_code != HTTP_OK:
            return None

        content = response.text

        # Parse YAML
        manifest_data = yaml.safe_load(content)

        # Check if ALL search terms are present (exact case, exact word matches)
        found_terms = set()
        match_locations = []

        for term in search_terms:
            locations = _find_term_in_yaml(manifest_data, term)
            if locations:
                found_terms.add(term)
                match_locations.extend(locations)

        # Only return if ALL terms were found
        if len(found_terms) == len(search_terms):
            # Extract connector name from path
            path_parts = result["path"].split("/")
            connector_name = "unknown"
            for part in path_parts:
                if part.startswith(("source-", "destination-")):
                    connector_name = part
                    break

            return ConnectorMatch(
                name=connector_name,
                repository=result["repository"]["full_name"],
                file_path=result["path"],
                github_url=result["html_url"],
                raw_url=result["download_url"],
                match_locations=match_locations
            )

    except Exception:
        # Skip files with invalid YAML or network errors
        pass

    return None


def _find_term_in_yaml(data: object, term: str, path: str = "") -> list[str]:
    """Find exact term matches in YAML structure and return their paths."""
    matches = []

    if isinstance(data, str):
        if term in data:  # Exact case, substring match
            display_value = (
                data[:MAX_DISPLAY_LENGTH] + "..."
                if len(data) > MAX_DISPLAY_LENGTH
                else data
            )
            matches.append(f"{path}: '{display_value}'")

    elif isinstance(data, dict):
        for key, value in data.items():
            new_path = f"{path}.{key}" if path else key

            # Check key names
            if term in key:
                matches.append(f"{new_path} (key)")

            # Check values
            matches.extend(_find_term_in_yaml(value, term, new_path))

    elif isinstance(data, list):
        for i, item in enumerate(data):
            new_path = f"{path}[{i}]"
            matches.extend(_find_term_in_yaml(item, term, new_path))

    return matches


def get_manifest_schema() -> GetManifestSchemaResponse:
    """Retrieve the connector manifest JSON schema from the Airbyte repository.

    Returns:
        Response containing the schema in YAML format
    """
    # URL to the manifest schema in the Airbyte Python CDK repository
    schema_url: str = "https://raw.githubusercontent.com/airbytehq/airbyte-python-cdk/refs/heads/main/airbyte_cdk/sources/declarative/declarative_component_schema.yaml"

    headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "connector-schema-tool"}

    try:
        response = requests.get(schema_url, headers=headers, timeout=30)
        if response.status_code == HTTP_OK:
            schema_content = response.text

            # Try to extract version from the schema if available
            version = "unknown"
            try:
                schema_data = yaml.safe_load(schema_content)
                if isinstance(schema_data, dict):
                    # Look for version information in common locations
                    version = (
                        schema_data.get("version")
                        or schema_data.get("info", {}).get("version")
                        or "latest"
                    )
            except Exception:
                version = "latest"

            return GetManifestSchemaResponse(
                schema_yaml=schema_content, schema_url=schema_url, version=version
            )

        # Fallback to alternative schema location
        alt_schema_url = "https://raw.githubusercontent.com/airbytehq/airbyte-python-cdk/main/airbyte_cdk/sources/declarative/declarative_component_schema.yaml"
        alt_response = requests.get(alt_schema_url, headers=headers, timeout=30)
        if alt_response.status_code == HTTP_OK:
            return GetManifestSchemaResponse(
                schema_yaml=alt_response.text, schema_url=alt_schema_url, version="latest"
            )

        raise SchemaRetrievalError(f"Failed to retrieve schema: HTTP {response.status_code}")

    except Exception as e:
        raise SchemaRetrievalError(f"Error retrieving manifest schema: {e!s}") from e


def register_connector_search_tools(mcp: "FastMCP") -> None:
    """Register connector search tools with the MCP server."""

    @mcp.tool()
    def search_connector_manifests_tool(
        search_terms: list[str],
        github_token: str | None = None
    ) -> SearchConnectorManifestsResponse:
        """Search for connectors containing all specified strings in their manifest.yaml files.

        Uses GitHub code search API to efficiently find manifest files, then downloads
        and checks each one for ALL search terms (exact case, substring matches).

        Args:
            search_terms: Array of strings that must all be present in the manifest.yaml file
            github_token: Optional GitHub token for authenticated requests (increases rate limits)

        Returns:
            Response with matching connectors and search metadata

        Example:
            # Find connectors using both HttpComponentsResolver and stream_config
            result = search_connector_manifests_tool(
                search_terms=["HttpComponentsResolver", "stream_config"]
            )
        """
        request = SearchConnectorManifestsRequest(
            search_terms=search_terms,
            github_token=github_token
        )
        return search_connector_manifests(request)

    @mcp.tool()
    def get_manifest_schema_tool() -> GetManifestSchemaResponse:
        """Retrieve the connector manifest JSON schema from the Airbyte repository.

        This tool fetches the official JSON schema used to validate connector manifests.
        The schema defines the structure, required fields, and validation rules for
        connector YAML configurations.

        Returns:
            Response containing the schema in YAML format, source URL, and version info

        Example:
            schema_result = get_manifest_schema_tool()
            print(f"Schema from: {schema_result.schema_url}")
            print(f"Version: {schema_result.version}")
        """
        return get_manifest_schema()
