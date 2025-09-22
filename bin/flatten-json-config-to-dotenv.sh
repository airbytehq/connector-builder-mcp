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
SECRETS_DIR="$JSON_DIR/secrets"

CONNECTOR_NAME=$(basename "$JSON_DIR")

mkdir -p "$SECRETS_DIR"

DOTENV_FILE="$SECRETS_DIR/${CONNECTOR_NAME}-config.env"

flatten_json() {
    local json="$1"
    
    echo "$json" | jq -r '
        def flatten:
            . as $in
            | reduce paths(scalars) as $path (
                {};
                . + { ($path | map(tostring) | join(".")): ($in | getpath($path)) }
            );
        flatten | to_entries[] | "\(.key)=\(.value)"
    '
}

echo "# Generated from $JSON_FILE" > "$DOTENV_FILE"
echo "# $(date)" >> "$DOTENV_FILE"
echo "# Connector: $CONNECTOR_NAME" >> "$DOTENV_FILE"
echo "" >> "$DOTENV_FILE"

JSON_CONTENT=$(cat "$JSON_FILE")
flatten_json "$JSON_CONTENT" >> "$DOTENV_FILE"

echo "Converted $JSON_FILE to $DOTENV_FILE"
echo "Dotenv file location: $DOTENV_FILE"
