"""Cost tracking module for multi-agent workflow execution.

This module provides functionality to track token usage and costs during
the execution of multi-agent workflows, with support for multiple models
and real-time cost calculation.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agents.result import RunResult


logger = logging.getLogger(__name__)


@dataclass
class ModelUsage:
    """Usage statistics for a specific model."""

    model_name: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    requests: int = 0
    estimated_cost: float = 0.0


@dataclass
class CostTracker:
    """Tracks costs and usage across multi-agent workflow execution."""

    trace_id: str
    model_usage: dict[str, ModelUsage] = field(default_factory=dict)
    total_estimated_cost: float = 0.0
    start_time: str | None = None
    end_time: str | None = None

    def add_run_result(self, run_result: RunResult) -> float:
        """Extract usage from RunResult and add to tracking.

        Args:
            run_result: The result from a Runner.run() call

        Returns:
            The estimated cost for this run result
        """
        run_cost = 0.0

        for response in run_result.raw_responses:
            if not response.usage:
                continue

            model_name = self._extract_model_name(response)

            if model_name not in self.model_usage:
                self.model_usage[model_name] = ModelUsage(model_name=model_name)

            usage_tracker = self.model_usage[model_name]

            usage_tracker.input_tokens += response.usage.input_tokens
            usage_tracker.output_tokens += response.usage.output_tokens
            usage_tracker.total_tokens += response.usage.total_tokens
            usage_tracker.requests += response.usage.requests

            response_cost = self._calculate_cost(model_name, response.usage)
            usage_tracker.estimated_cost += response_cost
            run_cost += response_cost

        self.total_estimated_cost += run_cost

        logger.info(
            f"[{self.trace_id}] Run tokens: {sum(response.usage.total_tokens for response in run_result.raw_responses if response.usage)}, "
            f"Total tokens: {sum(usage.total_tokens for usage in self.model_usage.values())}"
        )

        return run_cost

    def _extract_model_name(self, response: Any) -> str:
        """Extract model name from response object."""
        for attr in ["model", "model_name", "engine"]:
            if hasattr(response, attr):
                model_value = getattr(response, attr)
                if model_value:
                    return str(model_value)

        if hasattr(response, "raw_response"):
            raw = response.raw_response
            if hasattr(raw, "model"):
                return str(raw.model)

        return "unknown-model"

    def _calculate_cost(self, model_name: str, usage: Any) -> float:
        """Calculate estimated cost based on model and usage.

        Returns 0.0 for now - cost calculation can be implemented later
        with configurable pricing or actual API cost data.
        """
        return 0.0

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of all tracked usage and costs."""
        return {
            "trace_id": self.trace_id,
            "total_estimated_cost": self.total_estimated_cost,
            "total_tokens": sum(usage.total_tokens for usage in self.model_usage.values()),
            "total_requests": sum(usage.requests for usage in self.model_usage.values()),
            "models_used": list(self.model_usage.keys()),
            "model_breakdown": {
                name: {
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "total_tokens": usage.total_tokens,
                    "requests": usage.requests,
                    "estimated_cost": usage.estimated_cost,
                }
                for name, usage in self.model_usage.items()
            },
            "start_time": self.start_time,
            "end_time": self.end_time,
        }

    @property
    def cost_summary_report(self) -> str:
        """Generate a formatted summary report string."""
        cost_summary = self.get_summary()
        cost_evaluation = CostEvaluator.evaluate_cost_efficiency(self)

        lines = []
        lines.append("=" * 60)
        lines.append("🔢 TOKEN USAGE TRACKING SUMMARY")
        lines.append("=" * 60)
        lines.append(f"Total Tokens: {cost_summary['total_tokens']:,}")
        lines.append(f"Total Requests: {cost_summary['total_requests']}")
        lines.append(f"Models Used: {', '.join(cost_summary['models_used'])}")

        for model_name, model_data in cost_summary["model_breakdown"].items():
            lines.append(f"  {model_name}:")
            lines.append(f"    Input tokens: {model_data['input_tokens']:,}")
            lines.append(f"    Output tokens: {model_data['output_tokens']:,}")
            lines.append(f"    Requests: {model_data['requests']}")

        lines.append(f"\nUsage Status: {cost_evaluation['usage_status'].upper()}")
        if cost_evaluation["warnings"]:
            for warning in cost_evaluation["warnings"]:
                lines.append(f"⚠️  {warning}")
        if cost_evaluation["recommendations"]:
            for rec in cost_evaluation["recommendations"]:
                lines.append(f"💡 {rec}")

        lines.append("=" * 60)

        return "\n".join(lines)

    def save_to_file(self, output_path: Path | str) -> None:
        """Save cost tracking summary to a JSON file."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("w") as f:
            json.dump(self.get_summary(), f, indent=2)

        logger.info(f"Cost tracking summary saved to {output_path}")


class CostEvaluator:
    """Evaluates cost tracking results with business logic."""

    @staticmethod
    def evaluate_cost_efficiency(cost_tracker: CostTracker) -> dict[str, Any]:
        """Evaluate the cost efficiency of the workflow execution."""
        summary = cost_tracker.get_summary()

        thresholds = {
            "max_tokens_warning": 100000,  # Warn if tokens exceed 100K
            "max_tokens_critical": 500000,  # Critical if tokens exceed 500K
            "min_efficiency_ratio": 0.7,  # Minimum output/input token ratio
            "max_requests_warning": 100,  # Warn if requests exceed 100
        }

        evaluation = {
            "usage_status": "ok",
            "warnings": [],
            "recommendations": [],
            "efficiency_metrics": {},
        }

        total_tokens = summary["total_tokens"]
        total_requests = summary["total_requests"]

        if total_tokens > thresholds["max_tokens_critical"]:
            evaluation["usage_status"] = "critical"
            evaluation["warnings"].append(
                f"Token usage {total_tokens:,} exceeds critical threshold {thresholds['max_tokens_critical']:,}"
            )
        elif total_tokens > thresholds["max_tokens_warning"]:
            evaluation["usage_status"] = "warning"
            evaluation["warnings"].append(
                f"Token usage {total_tokens:,} exceeds warning threshold {thresholds['max_tokens_warning']:,}"
            )

        if total_requests > thresholds["max_requests_warning"]:
            evaluation["warnings"].append(
                f"Request count {total_requests} exceeds warning threshold {thresholds['max_requests_warning']}"
            )

        evaluation["efficiency_metrics"]["total_tokens"] = total_tokens
        evaluation["efficiency_metrics"]["total_requests"] = total_requests
        if total_requests > 0:
            tokens_per_request = total_tokens / total_requests
            evaluation["efficiency_metrics"]["tokens_per_request"] = tokens_per_request

        for model_name, model_data in summary["model_breakdown"].items():
            if model_data["input_tokens"] > 0:
                efficiency_ratio = model_data["output_tokens"] / model_data["input_tokens"]
                evaluation["efficiency_metrics"][f"{model_name}_efficiency"] = efficiency_ratio

                if efficiency_ratio < thresholds["min_efficiency_ratio"]:
                    evaluation["recommendations"].append(
                        f"{model_name}: Low output/input ratio {efficiency_ratio:.2f}, "
                        f"expected >{thresholds['min_efficiency_ratio']}"
                    )

        return evaluation
