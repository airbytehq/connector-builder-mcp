# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Run evaluations for connector builder agents using Phoenix.

This module executes automated evaluations of the connector builder agents
using the Phoenix evaluation framework. It runs experiments against a dataset
of connector building tasks and evaluates the quality of generated connectors
using multiple evaluation metrics.

Usage:
    poe evals run

Requirements:
    - OpenAI API key (OPENAI_API_KEY in a local '.env')
    - Phoenix API key (PHOENIX_API_KEY in a local '.env')
    - Phoenix collector endpoint (PHOENIX_COLLECTOR_ENDPOINT in a local '.env')
"""

import logging
import sys
import uuid

from dotenv import load_dotenv
from phoenix.client import AsyncClient
from phoenix.otel import register

from .dataset import get_or_create_phoenix_dataset
from .evaluators import READINESS_EVAL_MODEL, readiness_eval, streams_eval
from .summary import generate_markdown_summary
from .task import EVAL_DEVELOPER_MODEL, EVAL_MANAGER_MODEL, run_connector_build_task


load_dotenv()


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main(connectors: list[str] | None = None, *, dataset_prefix: str):
    logger.info("Registering Phoenix tracer")
    register(
        auto_instrument=True,
    )

    logger.info("Getting Phoenix dataset")
    dataset = get_or_create_phoenix_dataset(
        filtered_connectors=connectors, dataset_prefix=dataset_prefix
    )

    experiment_id = str(uuid.uuid4())[:5]
    experiment_name = f"builder-evals-{experiment_id}"
    evaluators = [readiness_eval, streams_eval]

    logger.info(f"Using evaluators: {[eval.__name__ for eval in evaluators]}")

    try:
        client = AsyncClient()
        logger.info(f"Starting experiment: {experiment_name}")
        experiment = await client.experiments.run_experiment(
            dataset=dataset,
            task=run_connector_build_task,
            evaluators=evaluators,
            experiment_name=experiment_name,
            experiment_metadata={
                "developer_model": EVAL_DEVELOPER_MODEL,
                "manager_model": EVAL_MANAGER_MODEL,
                "readiness_eval_model": READINESS_EVAL_MODEL,
            },
            timeout=1800,
        )
        logger.info(f"Experiment '{experiment_name}' completed successfully")

        task_runs = experiment.get("task_runs", [])
        failed_runs = [run for run in task_runs if run.get("error") is not None]

        if failed_runs:
            logger.error(
                f"Experiment had {len(failed_runs)} failed task run(s) out of {len(task_runs)} total"
            )
            for run in failed_runs:
                logger.error(f"  - Failed run {run.get('id')}: {run.get('error')}")
            logger.error("Exiting with non-zero code due to task failures")
            sys.exit(1)

        # Generate markdown summary
        summary_path = generate_markdown_summary(experiment, experiment_name)
        if summary_path:
            logger.info(f"Results summary available at: {summary_path}")

    except Exception as e:
        logger.error(f"Experiment '{experiment_name}' failed: {e}")
        raise
