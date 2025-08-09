#!/usr/bin/env python3
"""Build a searchable index of connector components from manifest.yaml files.

This script:
1. Shallow-checkouts the airbytehq/airbyte repo to a temp directory
2. Scans all manifest.yaml files in airbyte-integrations/connectors/source-*/
3. Extracts class names (ClassName format) using regex patterns
4. Creates a mapping of class names to connectors that use them

The resulting index can be used to find connectors using specific features or components.
"""

import csv
import re
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path


def shallow_checkout_airbyte_repo(temp_dir: Path) -> Path:
    """Shallow checkout the airbytehq/airbyte repo to a temporary directory.

    Args:
        temp_dir: Temporary directory to clone into

    Returns:
        Path to the cloned repository
    """
    repo_path = temp_dir / "airbyte"

    print(f"Shallow cloning airbytehq/airbyte to {repo_path}...")

    subprocess.run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "https://github.com/airbytehq/airbyte.git",
            str(repo_path),
        ],
        check=True,
        capture_output=True,
    )

    print(f"Successfully cloned airbyte repo to {repo_path}")
    return repo_path


def find_manifest_files(airbyte_repo_path: Path) -> list[Path]:
    """Find all manifest.yaml files in source connectors.

    Args:
        airbyte_repo_path: Path to the airbyte repository

    Returns:
        List of paths to manifest.yaml files
    """
    connectors_dir = airbyte_repo_path / "airbyte-integrations" / "connectors"

    if not connectors_dir.exists():
        raise FileNotFoundError(f"Connectors directory not found: {connectors_dir}")

    manifest_files = []

    for connector_dir in connectors_dir.glob("source-*"):
        if connector_dir.is_dir():
            manifest_file = connector_dir / "manifest.yaml"
            if manifest_file.exists():
                manifest_files.append(manifest_file)

    print(f"Found {len(manifest_files)} manifest.yaml files")
    return manifest_files


def extract_class_names_from_yaml(yaml_content: str) -> set[str]:
    """Extract class names (ClassName format) from YAML content using regex.

    This looks for 'type:' fields and other patterns that contain class names
    in PascalCase format.

    Args:
        yaml_content: Raw YAML content as string

    Returns:
        Set of unique class names found
    """
    class_names = set()

    type_pattern = r"type:\s*([A-Z][a-zA-Z0-9]*(?:[A-Z][a-zA-Z0-9]*)*)"

    for match in re.finditer(type_pattern, yaml_content):
        class_name = match.group(1)
        if class_name and len(class_name) > 1:  # Avoid single letters
            class_names.add(class_name)

    class_name_field_pattern = r"class_name:\s*([a-zA-Z_][a-zA-Z0-9_.]*\.)?([A-Z][a-zA-Z0-9]*)"
    for match in re.finditer(class_name_field_pattern, yaml_content):
        class_name = match.group(2)  # Get the class name part after the module
        if class_name and len(class_name) > 1:
            class_names.add(class_name)

    lines = yaml_content.split("\n")
    for line in lines:
        if line.strip().startswith("#"):
            continue

        value_matches = re.findall(
            r':\s*["\']?([A-Z][a-zA-Z0-9]*(?:[A-Z][a-zA-Z0-9]*)*)["\']?', line
        )
        for match in value_matches:
            if len(match) > 1:  # Avoid single letters
                class_names.add(match)

    return class_names


def extract_class_names_from_manifest(manifest_path: Path) -> set[str]:
    """Extract class names from a single manifest.yaml file.

    Args:
        manifest_path: Path to the manifest.yaml file

    Returns:
        Set of unique class names found in the manifest
    """
    try:
        with open(manifest_path, encoding="utf-8") as f:
            yaml_content = f.read()

        class_names = extract_class_names_from_yaml(yaml_content)

        filtered_class_names = set()
        false_positives = {
            "GET",
            "POST",
            "PUT",
            "DELETE",
            "PATCH",  # HTTP methods
            "JSON",
            "XML",
            "CSV",
            "API",
            "URL",
            "ID",
            "UUID",  # Common acronyms
            "UTC",
            "GMT",
            "ISO",
            "HTTP",
            "HTTPS",
            "SSL",
            "TLS",  # Technical terms
            "DEFAULT",
            "NULL",
            "TRUE",
            "FALSE",  # Constants
            "VERSION",
            "TYPE",
            "NAME",
            "VALUE",
            "KEY",  # Generic terms
        }

        for class_name in class_names:
            if (
                class_name not in false_positives
                and len(class_name) > 2
                and any(c.islower() for c in class_name)
            ):
                filtered_class_names.add(class_name)

        return filtered_class_names

    except Exception as e:
        print(f"Error processing {manifest_path}: {e}")
        return set()


def build_connector_index(manifest_files: list[Path]) -> list[tuple[str, str]]:
    """Build an index of feature usage by connectors.

    Args:
        manifest_files: List of paths to manifest.yaml files

    Returns:
        List of tuples (feature_name, connector_name) sorted by feature then connector
    """
    class_to_connectors = defaultdict(set)

    for manifest_path in manifest_files:
        connector_name = manifest_path.parent.name

        print(f"Processing {connector_name}...")

        class_names = extract_class_names_from_manifest(manifest_path)

        for class_name in class_names:
            class_to_connectors[class_name].add(connector_name)

    # Convert to list of tuples and sort
    result = []
    for class_name, connectors in class_to_connectors.items():
        for connector in sorted(connectors):
            result.append((class_name, connector))

    result.sort(key=lambda x: (x[0], x[1]))

    return result


def save_index(index: list[tuple[str, str]], output_path: Path) -> None:
    """Save the connector index to a CSV file.

    Args:
        index: List of tuples (feature_name, connector_name)
        output_path: Path where to save the index file
    """
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["FeatureUsage", "ConnectorName"])  # Header row
        writer.writerows(index)

    print(f"Index saved to {output_path}")


def print_summary(index: list[tuple[str, str]]) -> None:
    """Print a summary of the generated index.

    Args:
        index: List of tuples (feature_name, connector_name)
    """
    print("\n" + "=" * 60)
    print("CONNECTOR COMPONENT INDEX SUMMARY")
    print("=" * 60)

    # Count unique features and connectors
    features = {feature for feature, _ in index}
    connectors = {connector for _, connector in index}

    print(f"Total unique class names found: {len(features)}")
    print(f"Total connectors processed: {len(connectors)}")
    print(f"Total feature-connector pairs: {len(index)}")

    feature_counts = defaultdict(int)
    for feature, _ in index:
        feature_counts[feature] += 1

    print("\nTop 10 most commonly used class names:")
    sorted_by_usage = sorted(feature_counts.items(), key=lambda x: x[1], reverse=True)

    for i, (class_name, count) in enumerate(sorted_by_usage[:10], 1):
        print(f"{i:2d}. {class_name:<25} ({count:3d} connectors)")

    print("\nExample class name mappings:")
    for class_name, _ in sorted_by_usage[:3]:
        connectors_for_feature = [
            connector for feature, connector in index if feature == class_name
        ]
        print(f"\n{class_name}:")
        for connector in connectors_for_feature[:5]:  # Show first 5 connectors
            print(f"  - {connector}")
        if len(connectors_for_feature) > 5:
            print(f"  ... and {len(connectors_for_feature) - 5} more")


def main():
    """Main function to build the connector component index."""
    print("Building Airbyte Connector Component Index")
    print("=" * 50)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        try:
            airbyte_repo_path = shallow_checkout_airbyte_repo(temp_path)

            manifest_files = find_manifest_files(airbyte_repo_path)

            if not manifest_files:
                print("No manifest.yaml files found!")
                return

            print(f"\nBuilding index from {len(manifest_files)} manifest files...")
            index = build_connector_index(manifest_files)

            output_path = Path("generated/connector-feature-index.csv")
            save_index(index, output_path)

            print_summary(index)

            print("\n✅ Successfully built connector component index!")
            print(f"📁 Index saved to: {output_path.absolute()}")

        except Exception as e:
            print(f"❌ Error building index: {e}")
            raise


if __name__ == "__main__":
    main()
