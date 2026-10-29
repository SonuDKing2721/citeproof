"""Single source for Muse model settings used by calls and run reports."""

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
