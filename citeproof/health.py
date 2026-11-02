"""Small, bounded endpoint readiness check for the configured model route."""

import time
from collections.abc import Callable
from typing import Any

from .model_config import MODEL_ID


def check_endpoint(
    client: Any,
    *,
    timeout_seconds: float = 15,
    slow_after_seconds: float = 5,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, str | float | None]:
    """Send a five-token health request and report ready, slow, or unavailable."""
    if client is None:
        return {"status": "unavailable", "elapsed_seconds": 0, "error": "missing_api_key"}

    started = clock()
    try:
        client.chat.completions.create(
            model=MODEL_ID,
            messages=[{"role": "user", "content": "Reply with ready."}],
            max_tokens=5,
            temperature=0,
            timeout=timeout_seconds,
        )
    except Exception as exc:
        elapsed = max(0.0, round(clock() - started, 3))
        return {"status": "unavailable", "elapsed_seconds": elapsed, "error": type(exc).__name__}

    elapsed = max(0.0, round(clock() - started, 3))
    status = "slow" if elapsed > slow_after_seconds else "ready"
    return {"status": status, "elapsed_seconds": elapsed, "error": None}
