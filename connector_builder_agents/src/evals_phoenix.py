import logging
import os
import time
import uuid

import pandas as pd
import yaml
from dotenv import load_dotenv
from phoenix.client import Client
from phoenix.experiments import run_experiment
from phoenix.otel import register

from .evaluators import readiness_eval
from .run import get_workspace_dir, run_connector_build


# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()


logger.info("Registering Phoenix tracer for connector-builder-agent-evals")
tracer_provider = register(
    project_name="connector-builder-agent-evals",
    endpoint="https://app.phoenix.arize.com/s/pedro/v1/traces",
    auto_instrument=True,
)
logger.info("Phoenix tracer registered successfully")


dataset_id = uuid.uuid4()
dataset_name = "builder-connectors-" + str(uuid.uuid4())[:5]
logger.info(f"Generated dataset name: {dataset_name}")


def get_dataset() -> pd.DataFrame:
    logger.info("Loading connectors dataset from evals/connectors.yaml")
    try:
        with open("connector_builder_agents/evals/connectors.yaml") as f:
            connectors_config = yaml.safe_load(f)
            df = pd.DataFrame(connectors_config["connectors"])
            logger.info(f"Successfully loaded dataset with {len(df)} connectors")
            return df
    except Exception as e:
        logger.error(f"Failed to load dataset: {e}")
        raise


# Create dataset in Phoenix
logger.info("Creating Phoenix client and dataset")
# log api key
logger.info(f"Phoenix API key: {os.getenv('PHOENIX_API_KEY')}")
try:
    px_client = Client(
        api_key=os.getenv("PHOENIX_API_KEY"),
    )
    dataset = px_client.datasets.create_dataset(
        name=dataset_name, dataframe=get_dataset(), input_keys=["name", "prompt_name"]
    )
    logger.info(f"Successfully created Phoenix dataset: {dataset_name}")
except Exception as e:
    logger.error(f"Failed to create Phoenix dataset: {e}")
    raise


async def run_connector_build_task(dataset_row: dict) -> dict:
    connector_name = dataset_row.get("name", "unknown")
    prompt_name = dataset_row.get("prompt_name", "unknown")
    session_id = f"eval-{connector_name}-{int(time.time())}"

    logger.info(
        f"Starting connector build task for '{connector_name}' with prompt '{prompt_name}' (session: {session_id})"
    )

    try:
        build_result = await run_connector_build(
            api_name=prompt_name,
            session_id=session_id,
        )

        workspace_dir = get_workspace_dir(session_id)
        logger.info(f"Workspace directory: {workspace_dir}")

        final_result = build_result[-1] if build_result else None
        success = build_result is not None
        num_turns = len(build_result) if build_result else 0

        logger.info(f"Build completed - Success: {success}, Turns: {num_turns}")

        # Read readiness report if it exists
        readiness_report_path = workspace_dir / "connector-readiness-report.md"
        readiness_report_content = ""
        if readiness_report_path.exists():
            readiness_report_content = readiness_report_path.read_text(encoding="utf-8")
            logger.info(f"Found readiness report ({len(readiness_report_content)} characters)")
        else:
            readiness_report_content = "No readiness report found."
            logger.warning("No readiness report found")

        result = {
            "workspace_dir": str(workspace_dir.absolute()),
            "success": success,
            "final_output": final_result.final_output if final_result else None,
            "num_turns": num_turns,
            "messages": final_result.to_input_list() if final_result else [],
            "readiness_report_content": readiness_report_content,
        }

        logger.info(f"Task completed successfully for connector '{connector_name}'")
        return result

    except Exception as e:
        logger.error(f"Failed to build connector '{connector_name}': {e}")
        raise


experiment_id = str(uuid.uuid4())[:5]
experiment_name = f"builder-connector-evals-{experiment_id}"

logger.info(f"Starting experiment: {experiment_name}")
logger.info(f"Using evaluators: {[eval.__name__ for eval in [readiness_eval]]}")

try:
    experiment = run_experiment(
        dataset,
        task=run_connector_build_task,
        evaluators=[readiness_eval],
        experiment_name=experiment_name,
    )
    logger.info(f"Experiment '{experiment_name}' completed successfully")
except Exception as e:
    logger.error(f"Experiment '{experiment_name}' failed: {e}")
    raise
