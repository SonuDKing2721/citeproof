"""Run independent investigations concurrently while keeping UI callbacks on the caller thread."""

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from queue import Empty, Queue
from collections.abc import Callable

from .agent import MAX_COMPLETIONS_PER_AGENT, investigate
from .diagnostics import extract_reproducer_api_hints
from .models import AgentResult
from .repo import Repo

PAIR_STRATEGIES = (
    (
        "Investigator A · symptom-first",
        "Start from the observed behavior and exact expression. Search it, read the matching public method, then follow the call into the helper that owns the resource or behavior. Inspect the failing stack frame too when the report gives one.",
        "search_text",
    ),
    (
        "Investigator B · structure-first",
        "Start with the public API named in the issue reproducer. Read its implementation first, follow its calls into the helper that owns the behavior, and then use the failing stack frame and matching tests to confirm the link. A test-runner frame is context, not the target; do not spend both source reads in a test harness while the reproducer's product API is uninspected.",
        "find_symbols",
    ),
)


def investigate_pair(
    repo: Repo,
    issue: str,
    on_progress: Callable[[str, str], None] | None = None,
    investigator: Callable[..., AgentResult] = investigate,
    *,
    parallel: bool = True,
    max_completions: int = MAX_COMPLETIONS_PER_AGENT,
    preseed: str | None = None,
) -> tuple[AgentResult, AgentResult]:
    """Investigate independently in parallel and return stable A/B order.

    Worker callbacks enqueue plain progress strings. The optional callback is
    invoked only from this caller thread, which keeps Streamlit operations out
    of the model worker threads.
    """
    events: Queue[tuple[str, str]] = Queue()
    results: dict[str, AgentResult] = {}
    api_hints = extract_reproducer_api_hints(issue)
    repository_hints = repo.preseed_issue(issue) if preseed is None else preseed

    def run_one(strategy_spec: tuple[str, str, str], *, direct_progress: bool = False) -> AgentResult:
        label, strategy, first_tool = strategy_spec
        first_tool_query = (
            api_hints[0]
            if label == "Investigator B · structure-first" and api_hints
            else None
        )
        if first_tool_query:
            strategy += (
                f" The first structure search is fixed to the untrusted reproducer "
                f"API hint '{first_tool_query}'; verify it against source."
            )

        def enqueue(message: str) -> None:
            bounded = str(message)[:500]
            if direct_progress and on_progress:
                on_progress(label, bounded)
            else:
                events.put((label, bounded))

        try:
            return investigator(
                repo,
                issue,
                label,
                strategy,
                first_tool=first_tool,
                first_tool_query=first_tool_query,
                preseed=repository_hints,
                on_progress=enqueue,
                max_completions=max_completions,
            )
        except Exception as exc:
            return AgentResult(
                label,
                [],
                [],
                f"Investigation worker failed ({type(exc).__name__}); this result is incomplete.",
            )

    if not parallel:
        for spec in PAIR_STRATEGIES:
            results[spec[0]] = run_one(spec, direct_progress=True)
        return results[PAIR_STRATEGIES[0][0]], results[PAIR_STRATEGIES[1][0]]

    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="citeproof-investigator") as pool:
        future_to_name = {pool.submit(run_one, spec): spec[0] for spec in PAIR_STRATEGIES}
        pending = set(future_to_name)
        while pending:
            try:
                label, message = events.get(timeout=0.05)
                if on_progress:
                    on_progress(label, message)
            except Empty:
                pass
            completed, pending = wait(pending, timeout=0.05, return_when=FIRST_COMPLETED)
            for future in completed:
                label = future_to_name[future]
                results[label] = future.result()

        while True:
            try:
                label, message = events.get_nowait()
            except Empty:
                break
            if on_progress:
                on_progress(label, message)

    return results[PAIR_STRATEGIES[0][0]], results[PAIR_STRATEGIES[1][0]]
