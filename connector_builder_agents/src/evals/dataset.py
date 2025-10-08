# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Utilities for loading and creating the evals dataset."""

import hashlib
import json
import logging
from pathlib import Path

import pandas as pd
import yaml
from phoenix.client import Client
from phoenix.client.experiments import Dataset


logger = logging.getLogger(__name__)


def get_dataset_with_hash(connectors: list[str] | None = None) -> tuple[pd.DataFrame, str]:
    """Get the local evals dataset with a hash of the config.

    Args:
        connectors: Optional list of connector names to filter by.
    """

    # Get path relative to this file
    config_path = Path(__file__).parent / "data" / "connectors.yaml"
    logger.info(f"Loading connectors dataset from {config_path}")
    try:
        with open(config_path) as f:
            evals_config = yaml.safe_load(f)

            df = pd.DataFrame(evals_config["connectors"])

            # Filter by connector names if specified
            if connectors:
                original_count = len(df)
                df = df[df["name"].isin(connectors)]
                logger.info(
                    f"Filtered dataset from {original_count} to {len(df)} connectors "
                    f"(requested: {', '.join(connectors)})"
                )
                if len(df) == 0:
                    raise ValueError(
                        f"No connectors found matching: {', '.join(connectors)}. "
                        f"Available connectors: {', '.join(pd.DataFrame(evals_config['connectors'])['name'].tolist())}"
                    )

            # Compute hash based on the actual filtered data
            filtered_config = {"connectors": df.to_dict("records")}
            hash_value = hashlib.sha256(yaml.safe_dump(filtered_config).encode()).hexdigest()[:8]

            df["expected_streams"] = df["expected_streams"].apply(json.dumps)

            logger.info(
                f"Successfully loaded evals dataset with {len(df)} connectors (hash: {hash_value})"
            )
            return df, hash_value
    except Exception as e:
        logger.error(f"Failed to load dataset: {e}")
        raise


def get_or_create_phoenix_dataset(
    connectors: list[str] | None = None, *, dataset_prefix: str
) -> Dataset:
    """Get or create a Phoenix dataset for the evals config.

    Args:
        connectors: Optional list of connector names to filter by.
        dataset_prefix: Prefix for the dataset name.
    """
    dataframe, dataset_hash = get_dataset_with_hash(connectors=connectors)

    # Include connector names in dataset name for filtered datasets
    if connectors:
        connector_suffix = "-".join(sorted(connectors))[:30]  # Limit length
        dataset_name = f"{dataset_prefix}-{connector_suffix}-{dataset_hash}"
    else:
        dataset_name = f"{dataset_prefix}-{dataset_hash}"

    px_client = Client()

    try:
        dataset = px_client.datasets.get_dataset(dataset=dataset_name)
        logger.info(f"Reusing existing Phoenix dataset: {dataset_name}")
        return dataset
    except ValueError:
        logger.info(f"Creating new Phoenix dataset: {dataset_name}")
        return px_client.datasets.create_dataset(
            name=dataset_name,
            dataframe=dataframe,
            input_keys=["name", "prompt_name"],
            output_keys=["expected_streams"],
        )
