# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Evaluation framework for connector builder agents."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from agents.result import RunResult

from connector_builder_agents.src.constants import WORKSPACE_WRITE_DIR

from .run import run_connector_build


@dataclass
class EvaluationResult:
    """Result of evaluating a single connector build."""

    connector_name: str
    success: bool
    final_output: str
    error_message: str | None = None
    all_run_results: list[RunResult] | None = None  # All individual Runner.run results


class ConnectorEvaluator:
    """Evaluates connector builds using YAML configuration."""

    def __init__(self, config_path: str | Path):
        self.config_path = Path(config_path)
        self.config = self._load_config()

    def _load_config(self) -> dict[str, Any]:
        """Load evaluation configuration from YAML file."""
        with open(self.config_path) as f:
            return yaml.safe_load(f)

    async def evaluate_connector(
        self,
        connector_name: str,
        prompt_name: str,
        developer_model: str,
        manager_model: str,
    ) -> EvaluationResult:
        """Evaluate a single connector build."""
        try:
            results = await run_connector_build(
                api_name=prompt_name,
                developer_model=developer_model,
                manager_model=manager_model,
                interactive=False,
            )

            # Get final output from last result, or default message
            final_output = "No output captured"
            if results and len(results) > 0:
                final_output = results[-1].final_output

            return EvaluationResult(
                connector_name=connector_name,  # Used for file naming
                success=True,
                final_output=final_output,
                all_run_results=results,
            )
        except Exception as e:
            return EvaluationResult(
                connector_name=connector_name, success=False, final_output="", error_message=str(e)
            )

    async def evaluate_all(
        self,
        developer_model: str,
        manager_model: str,
    ) -> list[EvaluationResult]:
        """Evaluate all connectors in the configuration."""
        results = []
        connectors = self.config.get("connectors", [])

        for connector_config in connectors:
            connector_name = connector_config["name"]
            prompt_name = connector_config.get("prompt_name", connector_name)
            print(f"\n🧪 Evaluating connector: {prompt_name} ({connector_name})")

            result = await self.evaluate_connector(
                connector_name=connector_name,
                prompt_name=prompt_name,
                developer_model=developer_model,
                manager_model=manager_model,
            )
            results.append(result)

            print(
                f"✅ Completed evaluation for {prompt_name}: {'Success' if result.success else 'Failed'}"
            )

        return results

    def save_results(self, results: list[EvaluationResult], output_path: str | Path) -> None:
        """Save evaluation results to individual JSON files named by connector."""
        output_path = Path(output_path)
        output_dir = output_path.parent
        output_dir.mkdir(parents=True, exist_ok=True)

        for result in results:
            # Extract messages from all run results
            all_messages = []
            num_turns = 0

            if result.all_run_results:
                num_turns = len(result.all_run_results)
                for run_result in result.all_run_results:
                    run_messages = run_result.to_input_list() if run_result else []
                    all_messages.append(run_messages)

            serializable_result = {
                "connector_name": result.connector_name,
                "workspace_dir": str(WORKSPACE_WRITE_DIR.absolute()),
                "success": result.success,
                "final_output": result.final_output,
                "num_turns": num_turns,
                "all_messages": all_messages,  # List of message lists, one per turn
                "error_message": result.error_message,
            }

            # Create individual file for each connector
            connector_file = output_dir / f"{result.connector_name}.json"
            with open(connector_file, "w") as f:
                json.dump(serializable_result, f, indent=2)

            print(f"📊 Saved {result.connector_name} results to: {connector_file}")


async def run_evaluation(
    config_path: str = "connector_builder_agents/evals/connectors.yaml",
    output_path: str = "evals/results.json",
    developer_model: str = "gpt-4o-mini",
    manager_model: str = "gpt-4o",
) -> None:
    """Run the complete evaluation pipeline."""
    evaluator = ConnectorEvaluator(config_path)

    print("🚀 Starting connector evaluations...")
    results = await evaluator.evaluate_all(
        developer_model=developer_model,
        manager_model=manager_model,
    )

    evaluator.save_results(results, output_path)

    # Print summary
    successful = sum(1 for r in results if r.success)
    total = len(results)
    print(f"\n📈 Evaluation Summary: {successful}/{total} connectors successful")
