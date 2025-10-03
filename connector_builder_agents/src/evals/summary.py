# Copyright (c) 2025 Airbyte, Inc., all rights reserved.
"""Generate markdown summaries of evaluation results."""

import logging
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from phoenix.client import Client


logger = logging.getLogger(__name__)


def score_to_emoji(score: float) -> str:
    """Convert a score to a colored emoji indicator.

    Args:
        score: Score value between 0.0 and 1.0

    Returns:
        Emoji representing the score level
    """
    if score == 1.0:
        return "✅"
    elif score >= 0.75:
        return "🟢"
    elif score >= 0.5:
        return "🟡"
    elif score >= 0.25:
        return "🟠"
    elif score > 0.0:
        return "🔴"
    else:
        return "❌"


def find_prior_experiment(experiment: dict, client) -> dict | None:
    """Find the most recent prior experiment for the same dataset that has evaluation runs.

    Args:
        experiment: The current experiment
        client: Phoenix Client to fetch experiments

    Returns:
        Prior experiment dict or None if not found
    """
    if not client:
        return None

    try:
        dataset_id = experiment.get("dataset_id")
        if not dataset_id:
            return None

        # Fetch all experiments for this dataset
        response = client._client.get(f"v1/datasets/{dataset_id}/experiments")
        experiments_data = response.json().get("data", [])

        # Get current experiment start time
        current_exp_id = experiment.get("experiment_id")

        # Find experiments that are older than the current one
        prior_experiments = []
        for exp in experiments_data:
            if exp.get("id") != current_exp_id:
                prior_experiments.append(exp)

        if not prior_experiments:
            return None

        # Sort by created_at descending (most recent first)
        prior_experiments.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        # Find the first prior experiment that has evaluation runs
        for prior_exp in prior_experiments:
            prior_exp_id = prior_exp.get("id")
            full_prior = client.experiments.get_experiment(experiment_id=prior_exp_id)

            # Check if it has evaluation runs
            if full_prior.get("evaluation_runs"):
                logger.info(f"Found prior experiment with evaluations: {prior_exp_id}")
                return full_prior

        logger.info("No prior experiments with evaluation runs found")
        return None

    except Exception as e:
        logger.warning(f"Failed to fetch prior experiment: {e}")
        return None


def extract_scores_by_connector(experiment: dict, client) -> dict:
    """Extract scores organized by connector name and evaluator.

    Args:
        experiment: The experiment to extract scores from
        client: Phoenix Client to fetch additional data

    Returns:
        Dict mapping connector_name -> evaluator_name -> score
    """
    task_runs = experiment.get("task_runs", [])
    evaluation_runs = experiment.get("evaluation_runs", [])

    # Fetch JSON data to get connector names
    example_data_map = {}
    if client:
        try:
            experiment_id = experiment.get("experiment_id")
            json_response = client._client.get(f"v1/experiments/{experiment_id}/json")
            json_data = json_response.json()

            for record in json_data:
                example_id = record.get("example_id")
                input_data = record.get("input", {})
                example_data_map[example_id] = input_data.get(
                    "name", input_data.get("prompt_name", example_id)
                )
        except Exception as e:
            logger.warning(f"Failed to fetch connector names: {e}")

    # Build mapping of run_id to connector name
    run_to_connector = {}
    for run in task_runs:
        run_id = run["id"]
        example_id = run.get("dataset_example_id")
        connector_name = example_data_map.get(example_id, example_id)
        run_to_connector[run_id] = connector_name

    # Extract scores
    connector_scores = defaultdict(dict)
    for eval_run in evaluation_runs:
        run_id = eval_run.experiment_run_id
        eval_name = eval_run.name
        connector_name = run_to_connector.get(run_id)

        if not connector_name:
            continue

        result = eval_run.result
        score = None
        if result and isinstance(result, dict):
            score = result.get("score")
        elif result and isinstance(result, (list, tuple)) and len(result) > 0:
            first_result = result[0]
            if isinstance(first_result, dict):
                score = first_result.get("score")

        if score is not None:
            connector_scores[connector_name][eval_name] = score

    return connector_scores


def _generate_experiment_header(experiment: dict, client) -> list[str]:
    """Generate experiment header with ID and link."""
    md_lines = []
    experiment_id = experiment.get("experiment_id")
    dataset_id = experiment.get("dataset_id")

    if client and experiment_id and dataset_id:
        try:
            current_url = client.experiments.get_experiment_url(
                experiment_id=experiment_id, dataset_id=dataset_id
            )
            md_lines.extend(
                [
                    f"**Experiment:** [{experiment_id}]({current_url})",
                ]
            )
        except Exception as e:
            logger.warning(f"Failed to get current experiment URL: {e}")
            md_lines.extend(
                [
                    f"**Experiment ID:** `{experiment_id}`",
                ]
            )
    elif experiment_id:
        md_lines.extend(
            [
                f"**Experiment ID:** `{experiment_id}`",
            ]
        )

    # Add run date from earliest task run
    task_runs = experiment.get("task_runs", [])
    if task_runs:
        start_times = []
        for run in task_runs:
            start_time = run.get("start_time")
            if start_time:
                try:
                    if isinstance(start_time, str):
                        start_times.append(
                            datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                        )
                    else:
                        start_times.append(start_time)
                except Exception as e:
                    logger.warning(f"Failed to parse start_time: {e}")

        if start_times:
            earliest_start = min(start_times)
            formatted_date = earliest_start.strftime("%Y-%m-%d %H:%M UTC")
            md_lines.append("")
            md_lines.append(f"**Run Date:** {formatted_date}")

    md_lines.append("")
    return md_lines


def _generate_metadata_table(experiment_metadata: dict) -> list[str]:
    """Generate configuration metadata table."""
    if not experiment_metadata:
        return []

    md_lines = [
        "| Configuration | Value |",
        "|---------------|-------|",
    ]

    for key, value in sorted(experiment_metadata.items()):
        md_lines.append(f"| {key} | {value} |")

    md_lines.append("")
    return md_lines


def _generate_experiment_stats_table(eval_names: list[str], eval_scores: dict) -> list[str]:
    """Generate experiment statistics table with mean/min/max."""
    md_lines = [
        "## Experiment Stats",
        "",
        "| Evaluator | Mean | Min | Max |",
        "|-----------|------|-----|-----|",
    ]

    all_eval_means = []
    for eval_name in eval_names:
        # Collect all scores for this evaluator
        all_scores = []
        for scores in eval_scores[eval_name].values():
            if scores:
                all_scores.append(sum(scores) / len(scores))

        if not all_scores:
            continue

        mean_val = sum(all_scores) / len(all_scores)
        min_val = min(all_scores)
        max_val = max(all_scores)

        all_eval_means.append(mean_val)

        mean_emoji = score_to_emoji(mean_val)
        min_emoji = score_to_emoji(min_val)
        max_emoji = score_to_emoji(max_val)

        md_lines.append(
            f"| {eval_name} | {mean_emoji} {mean_val:.2f} | {min_emoji} {min_val:.2f} | {max_emoji} {max_val:.2f} |"
        )

    # Add overall row
    if all_eval_means:
        overall_mean = sum(all_eval_means) / len(all_eval_means)
        overall_emoji = score_to_emoji(overall_mean)
        md_lines.append(f"| **Overall** | **{overall_emoji} {overall_mean:.2f}** | | |")

    return md_lines


def _generate_score_distribution_table(
    eval_names: list[str], eval_scores: dict, run_data: dict
) -> list[str]:
    """Generate score distribution table."""
    # Calculate score distribution
    excellent = good = partial = poor = minimal = failed = 0

    for run_id, data in run_data.items():
        # Check if there's an error - count as failed
        if data.get("error"):
            failed += 1
            continue

        connector_scores = []
        for eval_name in eval_names:
            scores = eval_scores[eval_name].get(run_id, [])
            if scores:
                connector_scores.append(sum(scores) / len(scores))

        if connector_scores:
            overall_score = sum(connector_scores) / len(connector_scores)
            if overall_score == 1.0:
                excellent += 1
            elif overall_score >= 0.75:
                good += 1
            elif overall_score >= 0.5:
                partial += 1
            elif overall_score >= 0.25:
                poor += 1
            elif overall_score > 0.0:
                minimal += 1
            else:
                failed += 1
        else:
            # No scores available - count as failed
            failed += 1

    total = len(run_data)
    md_lines = [
        "",
        "| Score Level | Count | Percentage |",
        "|------------|-------|------------|",
    ]

    # Add rows for each score level that has results
    if excellent > 0:
        md_lines.append(f"| ✅ Excellent (1.0) | {excellent} | {excellent / total * 100:.0f}% |")
    if good > 0:
        md_lines.append(f"| 🟢 Good (0.75-0.99) | {good} | {good / total * 100:.0f}% |")
    if partial > 0:
        md_lines.append(f"| 🟡 Partial (0.5-0.74) | {partial} | {partial / total * 100:.0f}% |")
    if poor > 0:
        md_lines.append(f"| 🟠 Poor (0.25-0.49) | {poor} | {poor / total * 100:.0f}% |")
    if minimal > 0:
        md_lines.append(f"| 🔴 Minimal (0.01-0.24) | {minimal} | {minimal / total * 100:.0f}% |")
    if failed > 0:
        md_lines.append(f"| ❌ Failed (0.0) | {failed} | {failed / total * 100:.0f}% |")

    return md_lines


def _generate_per_connector_table(
    eval_names: list[str],
    eval_scores: dict,
    run_data: dict,
    prior_scores: dict,
    prior_experiment: dict | None,
    client,
) -> list[str]:
    """Generate per-connector results table."""
    md_lines = [
        "",
        "## Per-Connector Results",
        "",
    ]

    # Add comparison note if prior experiment exists
    if prior_experiment:
        prior_exp_id = prior_experiment.get("experiment_id", "unknown")
        prior_dataset_id = prior_experiment.get("dataset_id")
        prior_link = f"`{prior_exp_id}`"

        if client and prior_dataset_id:
            try:
                prior_url = client.experiments.get_experiment_url(
                    experiment_id=prior_exp_id, dataset_id=prior_dataset_id
                )
                prior_link = f"[{prior_exp_id}]({prior_url})"
            except Exception as e:
                logger.warning(f"Failed to get prior experiment URL: {e}")

        md_lines.extend(
            [
                f"_Comparing to prior experiment: {prior_link}_",
                "",
            ]
        )

    # Create table header
    connector_header = "| Connector | Duration |"
    separator = "|-----------|----------|"

    for eval_name in eval_names:
        connector_header += f" {eval_name} |"
        separator += "----------|"

    connector_header += " Overall |"
    separator += "---------|"

    md_lines.append(connector_header)
    md_lines.append(separator)

    # Sort connectors alphabetically
    sorted_runs = sorted(run_data.items(), key=lambda x: x[1].get("connector_name", x[0]))

    # Add row for each connector
    for run_id, data in sorted_runs:
        identifier = data.get("connector_name", run_id)
        row_line = f"| {identifier} |"

        # Add duration
        duration_seconds = data.get("duration_seconds")
        if duration_seconds is not None:
            minutes = int(duration_seconds // 60)
            seconds = int(duration_seconds % 60)
            row_line += f" {minutes}m {seconds}s |"
        else:
            row_line += " N/A |"

        # Add evaluator scores
        connector_scores = []
        for eval_name in eval_names:
            scores = eval_scores[eval_name].get(run_id, [])
            if scores:
                avg_score = sum(scores) / len(scores)
                connector_scores.append(avg_score)
                emoji = score_to_emoji(avg_score)

                # Calculate delta from prior
                delta_str = ""
                if (
                    prior_scores
                    and identifier in prior_scores
                    and eval_name in prior_scores[identifier]
                ):
                    prior_score = prior_scores[identifier][eval_name]
                    delta = avg_score - prior_score
                    if delta > 0:
                        delta_str = f" (↑ {delta:+.2f})"
                    elif delta < 0:
                        delta_str = f" (↓ {delta:+.2f})"
                    else:
                        delta_str = " (→)"

                row_line += f" {emoji} {avg_score:.2f}{delta_str} |"
            else:
                row_line += " N/A |"

        # Add overall score
        # Check if there's an error - show as failed
        if data.get("error"):
            row_line += " **❌ Error** |"
        elif connector_scores:
            overall_score = sum(connector_scores) / len(connector_scores)
            overall_emoji = score_to_emoji(overall_score)

            # Calculate prior overall
            overall_delta_str = ""
            if prior_scores and identifier in prior_scores:
                prior_connector_scores = [
                    prior_scores[identifier][eval_name]
                    for eval_name in eval_names
                    if eval_name in prior_scores[identifier]
                ]

                if prior_connector_scores:
                    prior_overall = sum(prior_connector_scores) / len(prior_connector_scores)
                    overall_delta = overall_score - prior_overall
                    if overall_delta > 0:
                        overall_delta_str = f" (↑ {overall_delta:+.2f})"
                    elif overall_delta < 0:
                        overall_delta_str = f" (↓ {overall_delta:+.2f})"
                    else:
                        overall_delta_str = " (→)"

            row_line += f" **{overall_emoji} {overall_score:.2f}**{overall_delta_str} |"
        else:
            row_line += " N/A |"

        md_lines.append(row_line)

    return md_lines


def _generate_errors_section(run_data: dict) -> list[str]:
    """Generate errors section showing failed runs."""
    md_lines = []

    # Collect errors
    errors = []
    for run_id, data in run_data.items():
        error = data.get("error")
        if error:
            connector_name = data.get("connector_name", run_id)
            errors.append({"connector": connector_name, "error": error})

    # Only add section if there are errors
    if errors:
        md_lines.extend([
            "",
            "## Errors",
            "",
        ])

        for error_info in errors:
            md_lines.extend([
                f"### {error_info['connector']}",
                "",
                "```",
                str(error_info['error']),
                "```",
                "",
            ])

    return md_lines


def generate_markdown_summary(experiment: dict, experiment_name: str) -> str | None:
    """Generate a markdown summary of experiment results.

    Args:
        experiment: The RanExperiment dict returned by run_experiment
        experiment_name: Name of the experiment

    Returns:
        Path to the generated markdown file
    """
    logger.info("Generating markdown summary")

    # Create Phoenix client
    client = Client()

    # Extract task runs and evaluation runs from the experiment
    task_runs = experiment.get("task_runs", [])
    evaluation_runs = experiment.get("evaluation_runs", [])

    if not task_runs:
        logger.warning("No task runs found in experiment")
        return None

    if not evaluation_runs:
        logger.warning("No evaluation runs found in experiment")
        return None

    # Find prior experiment for comparison
    prior_experiment = find_prior_experiment(experiment, client)
    prior_scores = {}
    if prior_experiment:
        prior_scores = extract_scores_by_connector(prior_experiment, client)

    # Fetch JSON data to get input details (including connector names)
    example_data_map = {}
    try:
        experiment_id = experiment.get("experiment_id")
        json_response = client._client.get(f"v1/experiments/{experiment_id}/json")
        json_data = json_response.json()

        for record in json_data:
            example_id = record.get("example_id")
            input_data = record.get("input", {})
            example_data_map[example_id] = {
                "name": input_data.get("name", input_data.get("prompt_name", example_id)),
                "input": input_data,
            }
    except Exception as e:
        logger.warning(f"Failed to fetch JSON data for input details: {e}")

    # Build a mapping from run_id to run data
    run_data = {}
    for run in task_runs:
        run_id = run["id"]
        example_id = run.get("dataset_example_id")

        # Get connector name from the example data if available
        if example_id in example_data_map:
            connector_name = example_data_map[example_id]["name"]
        else:
            # Fallback to trying input from task run
            input_data = run.get("input", {})
            connector_name = input_data.get(
                "name", input_data.get("prompt_name", example_id or run_id)
            )

        # Calculate execution time
        duration_seconds = None
        if run.get("start_time") and run.get("end_time"):
            try:
                start_time = run["start_time"]
                end_time = run["end_time"]

                # Parse if they're strings
                if isinstance(start_time, str):
                    start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                if isinstance(end_time, str):
                    end_time = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

                duration = end_time - start_time
                duration_seconds = duration.total_seconds()
            except Exception as e:
                logger.warning(f"Failed to calculate duration for run {run_id}: {e}")
                duration_seconds = None

        run_data[run_id] = {
            "connector_name": connector_name,
            "example_id": example_id,
            "output": run.get("output", {}),
            "error": run.get("error"),
            "duration_seconds": duration_seconds,
        }

    # Group evaluations by evaluator name and run_id
    eval_scores = defaultdict(lambda: defaultdict(list))
    eval_names = set()

    for eval_run in evaluation_runs:
        run_id = eval_run.experiment_run_id
        eval_name = eval_run.name
        eval_names.add(eval_name)

        # Get the score from the result
        result = eval_run.result
        score = None
        if result and isinstance(result, dict):
            score = result.get("score")
        elif result and isinstance(result, (list, tuple)) and len(result) > 0:
            # Handle list of results - take the first one
            first_result = result[0]
            if isinstance(first_result, dict):
                score = first_result.get("score")

        if score is not None:
            eval_scores[eval_name][run_id].append(score)

    if not eval_names:
        logger.warning("No evaluation scores found in results")
        return None

    eval_names = sorted(eval_names)

    # Build markdown document
    md_lines = ["# Evaluation Run Summary", ""]

    # Add sections
    md_lines.extend(_generate_experiment_header(experiment, client))
    md_lines.extend(_generate_metadata_table(experiment.get("experiment_metadata", {})))
    md_lines.extend(_generate_experiment_stats_table(eval_names, eval_scores))
    md_lines.extend(_generate_score_distribution_table(eval_names, eval_scores, run_data))
    md_lines.extend(
        _generate_per_connector_table(
            eval_names, eval_scores, run_data, prior_scores, prior_experiment, client
        )
    )
    md_lines.extend(_generate_errors_section(run_data))

    # Write to file
    output_dir = Path(__file__).parent / "results"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"{experiment_name}.md"

    markdown_content = "\n".join(md_lines)

    with open(output_path, "w") as f:
        f.write(markdown_content)

    logger.info(f"Markdown summary written to: {output_path}")

    # Write to GitHub step summary if running in CI
    github_step_summary = os.getenv("GITHUB_STEP_SUMMARY")
    if github_step_summary:
        try:
            with open(github_step_summary, "a") as f:
                f.write(markdown_content)
                f.write("\n")
            logger.info("Summary written to GitHub step summary")
        except Exception as e:
            logger.warning(f"Failed to write to GitHub step summary: {e}")

    return str(output_path)
