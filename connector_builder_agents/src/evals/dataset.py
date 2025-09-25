# Copyright (c) 2025 Airbyte, Inc., all rights reserved.

import hashlib
import logging

import pandas as pd
import yaml
from phoenix.client import Client
from phoenix.experiments.types import Dataset


logger = logging.getLogger(__name__)


def get_dataset_with_hash() -> tuple[pd.DataFrame, str]:
    """Get the local evals dataset with a hash of the config."""

    logger.info("Loading connectors dataset from connector_builder_agents/evals/connectors.yaml")
    try:
        with open("connector_builder_agents/evals/connectors.yaml") as f:
            evals_config = yaml.safe_load(f)
            hash_value = hashlib.sha256(yaml.safe_dump(evals_config).encode()).hexdigest()[:8]
            df = pd.DataFrame(evals_config["connectors"])
            logger.info(
                f"Successfully loaded evals dataset with {len(df)} connectors (hash: {hash_value})"
            )
            return df, hash_value
    except Exception as e:
        logger.error(f"Failed to load dataset: {e}")
        raise


def get_or_create_phoenix_dataset() -> Dataset:
    """Get or create a Phoenix dataset for the evals config."""
    dataframe, dataset_hash = get_dataset_with_hash()
    dataset_name = f"builder-connectors-{dataset_hash}"

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
            input_keys=["name", "prompt_name", "expected_streams"],
        )
