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

_THRESHOLDS = {
    "max_tokens_warning": 1_000_000,  # Warn if tokens exceed 1M
    "max_tokens_critical": 2_000_000,  # Critical if tokens exceed 2M
    "min_efficiency_ratio": 0.7,  # Minimum output/input token ratio
    "max_requests_warning": 100,  # Warn if requests exceed 100
}

_MODEL_PRICING = {
    """Pricing per 1M tokens in USD as of September 2024.

    Each model maps to a tuple of (input_price_per_1M_tokens, output_price_per_1M_tokens).
    Prices are based on official API documentation from OpenAI, Anthropic, and other providers.

    Example: "gpt-4o": (2.5, 10.0) means $2.50 per 1M input tokens, $10.00 per 1M output tokens.
    """
    "gpt-4": (30.0, 60.0),
    "gpt-4-turbo": (10.0, 30.0),
    "gpt-4o": (2.5, 10.0),
    "gpt-4o-mini": (0.15, 0.6),
    "gpt-4-32k": (60.0, 120.0),
    "gpt-4-1106-preview": (10.0, 30.0),
    "gpt-4-0125-preview": (10.0, 30.0),
    "gpt-4-turbo-preview": (10.0, 30.0),
    "gpt-4-vision-preview": (10.0, 30.0),
    "gpt-4-turbo-2024-04-09": (10.0, 30.0),
    "gpt-4o-2024-05-13": (5.0, 15.0),
    "gpt-4o-2024-08-06": (2.5, 10.0),
    "gpt-3.5-turbo": (0.5, 1.5),
    "gpt-3.5-turbo-16k": (3.0, 4.0),
    "gpt-3.5-turbo-1106": (1.0, 2.0),
    "gpt-3.5-turbo-0125": (0.5, 1.5),
    "o1-preview": (15.0, 60.0),
    "o1-mini": (3.0, 12.0),
    "gpt-5": (20.0, 80.0),  # Estimated pricing for future model
    "o4-mini": (2.0, 8.0),  # Estimated pricing for future model
    "claude-3-opus": (15.0, 75.0),
    "claude-3-sonnet": (3.0, 15.0),
    "claude-3-haiku": (0.25, 1.25),
    "claude-3-5-sonnet": (3.0, 15.0),
    "unknown-model": (10.0, 30.0),  # Conservative estimate
}


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

        # Try nested raw_response
        if hasattr(response, "raw_response"):
            raw = response.raw_response
            if hasattr(raw, "model"):
                model_value = raw.model
                if model_value:
                    return str(model_value)

        if hasattr(response, "response"):
            resp = response.response
            if hasattr(resp, "model"):
                model_value = resp.model
                if model_value:
                    return str(model_value)

        if hasattr(response, "__getitem__"):
            try:
                if "model" in response:
                    return str(response["model"])
            except (TypeError, KeyError):
                pass

        if hasattr(response, "choices") and response.choices:
            choice = response.choices[0]
            if hasattr(choice, "message") and hasattr(choice.message, "model"):
                model_value = choice.message.model
                if model_value:
                    return str(model_value)

        logger.debug(
            f"Could not extract model name from response. Available attributes: {dir(response)}"
        )
        if hasattr(response, "raw_response"):
            logger.debug(f"Raw response attributes: {dir(response.raw_response)}")

        return "unknown-model"

    def _calculate_cost(self, model_name: str, usage: Any) -> float:
        """Calculate estimated cost based on model and usage.

        Args:
            model_name: Name of the model used
            usage: Usage object with input_tokens and output_tokens

        Returns:
            Estimated cost in USD
        """
        if not hasattr(usage, "input_tokens") or not hasattr(usage, "output_tokens"):
            logger.warning(f"Usage object missing token counts for model {model_name}")
            return 0.0

        input_tokens = getattr(usage, "input_tokens", 0)
        output_tokens = getattr(usage, "output_tokens", 0)

        if input_tokens == 0 and output_tokens == 0:
            return 0.0

        input_price_per_1m, output_price_per_1m = _MODEL_PRICING.get(
            model_name, _MODEL_PRICING["unknown-model"]
        )

        input_cost = (input_tokens / 1_000_000) * input_price_per_1m
        output_cost = (output_tokens / 1_000_000) * output_price_per_1m
        total_cost = input_cost + output_cost

        logger.debug(
            f"Cost calculation for {model_name}: "
            f"{input_tokens:,} input tokens (${input_cost:.6f}) + "
            f"{output_tokens:,} output tokens (${output_cost:.6f}) = "
            f"${total_cost:.6f}"
        )

        return total_cost

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
        lines.append(f"Total Estimated Cost: ${cost_summary['total_estimated_cost']:.4f}")
        lines.append(f"Models Used: {', '.join(cost_summary['models_used'])}")

        for model_name, model_data in cost_summary["model_breakdown"].items():
            lines.append(f"  {model_name}:")
            lines.append(f"    Input tokens: {model_data['input_tokens']:,}")
            lines.append(f"    Output tokens: {model_data['output_tokens']:,}")
            lines.append(f"    Requests: {model_data['requests']}")
            lines.append(f"    Estimated cost: ${model_data['estimated_cost']:.4f}")

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
        evaluation = {
            "usage_status": "ok",
            "warnings": [],
            "recommendations": [],
            "efficiency_metrics": {},
        }

        total_tokens = summary["total_tokens"]
        total_requests = summary["total_requests"]

        if total_tokens > _THRESHOLDS["max_tokens_critical"]:
            evaluation["usage_status"] = "critical"
            evaluation["warnings"].append(
                f"Token usage {total_tokens:,} exceeds critical threshold {_THRESHOLDS['max_tokens_critical']:,}"
            )
        elif total_tokens > _THRESHOLDS["max_tokens_warning"]:
            evaluation["usage_status"] = "warning"
            evaluation["warnings"].append(
                f"Token usage {total_tokens:,} exceeds warning threshold {_THRESHOLDS['max_tokens_warning']:,}"
            )

        if total_requests > _THRESHOLDS["max_requests_warning"]:
            evaluation["warnings"].append(
                f"Request count {total_requests} exceeds warning threshold {_THRESHOLDS['max_requests_warning']}"
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

                if efficiency_ratio < _THRESHOLDS["min_efficiency_ratio"]:
                    evaluation["recommendations"].append(
                        f"{model_name}: Low output/input ratio {efficiency_ratio:.2f}, "
                        f"expected >{_THRESHOLDS['min_efficiency_ratio']}"
                    )

        return evaluation
