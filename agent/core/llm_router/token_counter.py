"""Token counting utilities for the LLM router."""

from __future__ import annotations

# Cost per 1M tokens (input, output)
MODEL_COSTS: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-20250514": (3.0, 15.0),
    "claude-haiku-4-5-20251001": (1.0, 5.0),
    "claude-haiku-3-20240307": (0.25, 1.25),
    "gpt-4o": (2.5, 10.0),
    "gpt-4o-mini": (0.15, 0.6),
    "gpt-4.1-nano": (0.20, 0.80),
    "gemini-2.0-flash": (0.1, 0.4),
    "text-embedding-3-small": (0.02, 0.0),
}


def estimate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """Estimate the cost of an LLM call in USD."""
    # Direct lookup first
    if model in MODEL_COSTS:
        costs = MODEL_COSTS[model]
    else:
        # Try to find partial match
        costs = None
        for model_key, cost_pair in MODEL_COSTS.items():
            # Check if the model string contains the key or vice versa
            if model_key in model or model in model_key:
                costs = cost_pair
                break

        if costs is None:
            # Log warning about unknown model
            print(f"Warning: Unknown model '{model}', using default costs")
            # Default to a mid-range estimate
            costs = (3.0, 15.0)

    input_cost = (input_tokens / 1_000_000) * costs[0]
    output_cost = (output_tokens / 1_000_000) * costs[1]
    return input_cost + output_cost
