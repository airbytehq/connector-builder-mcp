import hashlib
import logging
import time
import uuid

import pandas as pd
import yaml
from dotenv import load_dotenv
from openinference.instrumentation.openai_agents import OpenAIAgentsInstrumentor
from phoenix.client import Client
from phoenix.experiments import run_experiment
from phoenix.otel import register

from .evaluators import expected_streams_eval, readiness_eval
from .run import get_workspace_dir, run_connector_build


# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()


def calculate_connectors_hash() -> str:
    """Calculate SHA256 hash of the connectors.yaml file."""
    try:
        with open("connector_builder_agents/evals/connectors.yaml", "rb") as f:
            content = f.read()
            hash_value = hashlib.sha256(content).hexdigest()[:8]  # Use first 8 chars for brevity
            logger.info(f"Calculated connectors.yaml hash: {hash_value}")
            return hash_value
    except Exception as e:
        logger.error(f"Failed to calculate connectors.yaml hash: {e}")
        raise


def dataset_exists(px_client: Client, dataset_name: str) -> bool:
    """Check if a dataset with the given name exists."""
    try:
        px_client.datasets.get_dataset(dataset=dataset_name)
        logger.info(f"Dataset exists: {dataset_name}")
        return True
    except Exception as e:
        logger.info(f"Dataset does not exist: {dataset_name} (error: {e})")
        return False


logger.info("Registering Phoenix tracer for connector-builder-agent-evals")
tracer_provider = register(
    project_name="connector-builder-agent-evals",
    auto_instrument=True,
)
OpenAIAgentsInstrumentor().instrument(tracer_provider=tracer_provider)
logger.info("Phoenix tracer registered successfully")


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


# Create or reuse dataset in Phoenix based on connectors.yaml hash
logger.info("Creating Phoenix client and checking for existing dataset")
try:
    px_client = Client()
    connectors_hash = calculate_connectors_hash()
    dataset_name = f"builder-connectors-{connectors_hash}"

    if dataset_exists(px_client, dataset_name):
        # Reuse existing dataset
        dataset = px_client.datasets.get_dataset(dataset=dataset_name)
        logger.info(f"Reusing existing Phoenix dataset: {dataset_name}")
    else:
        # Create new dataset
        try:
            dataset = px_client.datasets.create_dataset(
                name=dataset_name,
                dataframe=get_dataset(),
                input_keys=["name", "prompt_name", "expected_streams"],
            )
            logger.info(f"Successfully created new Phoenix dataset: {dataset_name}")
        except Exception as e:
            # If creation fails due to dataset already existing, try to get it
            if "already exists" in str(e) or "409" in str(e):
                logger.info(
                    f"Dataset creation failed because it already exists, attempting to retrieve: {dataset_name}"
                )
                dataset = px_client.datasets.get_dataset(name=dataset_name)
                logger.info(f"Successfully retrieved existing Phoenix dataset: {dataset_name}")
            else:
                raise

except Exception as e:
    logger.error(f"Failed to create or retrieve Phoenix dataset: {e}")
    raise


def get_artifact(workspace_dir, artifact_name: str, logger) -> str | None:
    """Read an artifact file from the workspace directory."""
    artifact_path = workspace_dir / artifact_name
    if artifact_path.exists():
        content = artifact_path.read_text(encoding="utf-8")
        logger.info(f"Found {artifact_name} ({len(content)} characters)")
        return content
    else:
        logger.warning(f"No {artifact_name} found")
        return None


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

        # Read artifacts
        readiness_report_content = get_artifact(
            workspace_dir, "connector-readiness-report.md", logger
        )
        manifest_content = get_artifact(workspace_dir, "manifest.yaml", logger)

        result = {
            "workspace_dir": str(workspace_dir.absolute()),
            "success": success,
            "final_output": final_result.final_output if final_result else None,
            "num_turns": num_turns,
            "messages": final_result.to_input_list() if final_result else [],
            "artifacts": {
                "readiness_report": readiness_report_content,
                "manifest": manifest_content,
            },
        }

        logger.info(f"Task completed successfully for connector '{connector_name}'")
        return result

    except Exception as e:
        logger.error(f"Failed to build connector '{connector_name}': {e}")
        raise


experiment_id = str(uuid.uuid4())[:5]
experiment_name = f"builder-connector-evals-{experiment_id}"

logger.info(f"Starting experiment: {experiment_name}")
logger.info(
    f"Using evaluators: {[eval.__name__ for eval in [readiness_eval, expected_streams_eval]]}"
)

try:
    experiment = run_experiment(
        dataset,
        task=run_connector_build_task,
        evaluators=[readiness_eval, expected_streams_eval],
        experiment_name=experiment_name,
        timeout=1800,
    )
    logger.info(f"Experiment '{experiment_name}' completed successfully")
except Exception as e:
    logger.error(f"Experiment '{experiment_name}' failed: {e}")
    raise
