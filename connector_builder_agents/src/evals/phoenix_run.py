# Copyright (c) 2025 Airbyte, Inc., all rights reserved.

import logging
import uuid

from dotenv import load_dotenv
from phoenix.experiments import run_experiment
from phoenix.otel import register

from .dataset import get_or_create_phoenix_dataset
from .evaluators import READINESS_EVAL_MODEL, readiness_eval, streams_eval
from .task import EVAL_DEVELOPER_MODEL, EVAL_MANAGER_MODEL, run_connector_build_task


load_dotenv()


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


logger.info("Registering Phoenix tracer")
register(
    auto_instrument=True,
)


logger.info("Getting Phoenix dataset")
dataset = get_or_create_phoenix_dataset()

experiment_id = str(uuid.uuid4())[:5]
experiment_name = f"builder-evals-{experiment_id}"
evaluators = [readiness_eval, streams_eval]

logger.info(f"Using evaluators: {[eval.__name__ for eval in evaluators]}")


try:
    logger.info(f"Starting experiment: {experiment_name}")
    experiment = run_experiment(
        dataset,
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
except Exception as e:
    logger.error(f"Experiment '{experiment_name}' failed: {e}")
    raise
