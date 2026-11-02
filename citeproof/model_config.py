"""Model settings and opt-in inference profiles used by Citeproof."""

from dataclasses import dataclass
import re

MODEL_ID = "meta/muse-glimmer-30b"
MODEL_REQUEST_TIMEOUT_SECONDS = 120.0
AGENT_TIME_BUDGET_SECONDS = 240.0

INVESTIGATOR_REQUEST_SETTINGS = {
    "max_tokens": 8192,
    "temperature": 0.95,
    "top_p": 1.0,
    "reasoning_effort": "low",
}

VERIFIER_REQUEST_SETTINGS = {
    "max_tokens": 1800,
    "temperature": 0.2,
    "top_p": 1.0,
    "reasoning_effort": "low",
}


@dataclass(frozen=True)
class InferenceProfile:
    """A model endpoint configuration injected only by the benchmark CLI."""

    provider: str
    model_id: str
    base_url: str
    api_key: str
    request_settings: dict[str, object]
    timeout_seconds: float = MODEL_REQUEST_TIMEOUT_SECONDS
    time_budget_seconds: float = AGENT_TIME_BUDGET_SECONDS
    supports_forced_tool_choice: bool = True
    max_completions: int = 4


def ollama_profile(model_id: str) -> InferenceProfile:
    """Create a strictly local, no-credential profile for an installed Ollama model."""
    if not isinstance(model_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}", model_id):
        raise ValueError("Ollama model name is invalid.")
    if "cloud" in model_id.casefold():
        raise ValueError("Ollama cloud models are excluded; select an installed local model.")
    return InferenceProfile(
        provider="Ollama local",
        model_id=model_id,
        base_url="http://127.0.0.1:11434/v1",
        api_key="ollama",
        request_settings={"max_tokens": 2048, "temperature": 0.2, "top_p": 0.9},
        timeout_seconds=120.0,
        time_budget_seconds=240.0,
        supports_forced_tool_choice=False,
        max_completions=4,
    )
