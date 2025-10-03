# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Demo script to generate markdown summary for an existing experiment.

Usage:
    python -m connector_builder_agents.src.evals.generate_summary_demo
"""

import logging

from dotenv import load_dotenv
from phoenix.client import Client

from .summary import generate_markdown_summary


load_dotenv()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    # Set your experiment ID or name here
    experiment_id = "RXhwZXJpbWVudDoyNg=="  # Can be ID or name like "builder-evals-abc12"

    logger.info(f"Fetching experiment: {experiment_id}")

    client = Client()

    try:
        # Try to get experiment by ID or name
        experiment = client.experiments.get_experiment(experiment_id=experiment_id)
        logger.info(f"Successfully fetched experiment: {experiment_id}")

        # Generate markdown summary
        summary_path = generate_markdown_summary(experiment, experiment_id, client=client)

        if summary_path:
            logger.info(f"✓ Summary generated successfully at: {summary_path}")
        else:
            logger.error("Failed to generate summary")

    except Exception as e:
        logger.error(f"Error fetching or processing experiment: {e}")
        raise


if __name__ == "__main__":
    main()
