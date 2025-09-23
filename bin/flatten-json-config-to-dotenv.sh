#!/bin/bash


set -euo pipefail

if [ $# -eq 0 ]; then
    echo "Usage: $0 <json_file>" >&2
    echo "Converts JSON config to dotenv format with flattened keys" >&2
    echo "Creates dotenv file in secrets subfolder with connector-specific naming" >&2
    exit 1
fi

JSON_FILE="$1"

if [ ! -f "$JSON_FILE" ]; then
    echo "Error: File '$JSON_FILE' not found" >&2
    exit 1
fi

JSON_DIR=$(dirname "$JSON_FILE")
SECRETS_DIR="$JSON_DIR"

CONNECTOR_NAME=$(basename "$(dirname "$JSON_DIR")")
# Get short connector name by removing prefix up to first hyphen and replacing hyphens with underscores
# E.g., "source-postgres" -> "postgres", "destination-s3" -> "s3", "source-mysql-advanced" -> "mysql_advanced"
CONNECTOR_NAME_SHORT=$(echo "$CONNECTOR_NAME" | sed -E 's/^[^-]+-//' | tr '-' '_')

mkdir -p "$SECRETS_DIR"

DOTENV_FILE="$SECRETS_DIR/${CONNECTOR_NAME}-config.env"



# Filter function: returns 1 to include, 0 to exclude. Default: only include keys with 'CREDENTIALS'.
filter_key() {
    local key="$1"
    if [[ "$key" == *CREDENTIALS* ]]; then
        if [[ "$key" == *"_CREDENTIALS_CREDENTIALS_TITLE"* ]]; then
            return 1  # Exclude keys that are just titles
        fi
        return 0
    else
        return 1
    fi
}

# Flatten JSON and apply filter function to each key
flatten_json() {
    local json="$1"
    local filter_func=${2:-filter_key}

    # Use jq to flatten, then filter in bash
    local prefix_upper
    prefix_upper=$(echo "${CONNECTOR_NAME_SHORT}_" | tr '[:lower:]' '[:upper:]')
    echo "$json" | jq -r --arg prefix "$prefix_upper" '
        def flatten:
            . as $in
            | reduce paths(scalars) as $path (
                {};
                . + { ($path | map(tostring) | join(".")): ($in | getpath($path)) }
            );
        flatten
        | to_entries[]
        | "\($prefix)\(.key | gsub("\\."; "_") | ascii_upcase)=\(.value)"
    ' | while IFS= read -r line; do
        key=${line%%=*}
        value=${line#*=}
        if $filter_func "$key"; then
            echo "$key=$value"
        fi
    done
}

echo "# Generated from $JSON_FILE" > "$DOTENV_FILE"
echo "# $(date)" >> "$DOTENV_FILE"
echo "# Connector: $CONNECTOR_NAME" >> "$DOTENV_FILE"
echo "" >> "$DOTENV_FILE"

JSON_CONTENT=$(cat "$JSON_FILE")
flatten_json "$JSON_CONTENT" >> "$DOTENV_FILE"

echo "Converted $JSON_FILE" >&2
echo "to $DOTENV_FILE" >&2
echo "Dotenv file location: " >&2
echo "$DOTENV_FILE"
