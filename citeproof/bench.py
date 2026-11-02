"""Run a bounded comparison on one curated case and one provider/model."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Callable

from dotenv import load_dotenv

from .agent import MAX_COMPLETIONS_PER_AGENT, MODEL_ID, investigate
from .benchmark import run_benchmark_cli
from .cases import CASE_MANIFEST, load_curated_case
from .model_config import InferenceProfile, ollama_profile
from .verifier import verify_findings


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CASE_SLUGS = tuple(slug for _, slug, _ in CASE_MANIFEST)


def parse_local_models(output: str) -> list[str]:
    """Parse installed local models from `ollama list`, excluding cloud aliases."""
    models: list[str] = []
    for line in output.splitlines()[1:]:
        fields = line.split()
        if not fields:
            continue
        name = fields[0]
        if "cloud" in name.casefold() or name in models:
            continue
        models.append(name)
    return models


def parse_model_tool_support(output: str) -> bool:
    """Read Ollama model metadata; an agentic run needs the tools capability."""
    if not isinstance(output, str) or "Capabilities" not in output:
        return False
    section = output.split("Capabilities", 1)[1].split("Parameters", 1)[0]
    return any(line.strip().casefold() == "tools" for line in section.splitlines())


def list_local_models() -> list[str]:
    """Read model names from the local Ollama CLI; make no inference request."""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError(f"Could not read the local Ollama model list: {type(exc).__name__}.") from exc
    return parse_local_models(result.stdout)


def local_model_supports_tools(model_id: str) -> bool:
    """Check local model metadata without loading it or issuing inference."""
    try:
        result = subprocess.run(
            ["ollama", "show", model_id],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError(f"Could not inspect the local model capability: {type(exc).__name__}.") from exc
    return parse_model_tool_support(result.stdout)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-") or "model"


def default_output_path(root: Path, case_slug: str, model_id: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return root / "data" / "benchmarks" / f"{case_slug}-{_slug(model_id)}-{stamp}-comparison.json"


def _local_model_settings(profile: InferenceProfile) -> dict:
    return {
        "investigator": {
            "model_id": profile.model_id,
            "request_parameters": dict(profile.request_settings),
            "timeout_seconds": profile.timeout_seconds,
        },
        "verifier": {
            "model_id": profile.model_id,
            "request_parameters": {},
            "timeout_seconds": None,
            "status": "not_run; local model sweep omits the extra verifier call",
        },
    }


def main(
    argv: list[str] | None = None,
    *,
    root: str | Path | None = None,
    local_models: list[str] | None = None,
    model_capabilities: dict[str, bool] | None = None,
    runner: Callable | None = None,
) -> int:
    """CLI entrypoint. Injectable dependencies keep all CLI tests offline."""
    load_dotenv()
    project_root = Path(root) if root is not None else PROJECT_ROOT
    benchmark_runner = runner or run_benchmark_cli
    parser = argparse.ArgumentParser(
        description="Run a request-budget comparison on one pinned Citeproof case."
    )
    parser.add_argument("--case", required=True, choices=CASE_SLUGS, help="Curated issue case slug")
    parser.add_argument("--provider", choices=("nvidia", "ollama"), default="nvidia")
    parser.add_argument("--model", help="Required for --provider ollama; use an installed local model name")
    parser.add_argument("--output", type=Path, help="Output report path (must not already exist)")
    parser.add_argument(
        "--max-completions",
        type=int,
        choices=range(3, MAX_COMPLETIONS_PER_AGENT + 1),
        help="Per investigator completion cap (minimum 3 so a tool round remains before synthesis)",
    )
    args = parser.parse_args(argv)

    try:
        selected = load_curated_case(project_root, args.case)
        issue_path = project_root / "data" / "issues" / f"{args.case}.json"
        gold_path = project_root / "data" / "gold" / f"{args.case}.json"
        repo_path = project_root / "demo_repos" / selected["repo_dir"]
        if not repo_path.is_dir():
            raise ValueError(
                f"Pinned checkout is missing: {repo_path}. Run python scripts/setup_demo_repos.py first."
            )

        model_id = MODEL_ID
        provider = "NVIDIA API Catalog"
        investigator = investigate
        verifier = verify_findings
        parallel_pair = True
        model_settings = None
        if args.provider == "nvidia":
            if args.model:
                raise ValueError("--model is only accepted with --provider ollama.")
            if not os.getenv("NVIDIA_API_KEY", "").strip():
                raise ValueError("NVIDIA_API_KEY is not set; no model request was made.")
        else:
            if not args.model:
                raise ValueError("--provider ollama requires --model.")
            installed_models = local_models if local_models is not None else list_local_models()
            if args.model not in installed_models:
                raise ValueError("Selected model is not installed locally; cloud model names are excluded.")
            supports_tools = (
                model_capabilities.get(args.model, False)
                if model_capabilities is not None
                else local_model_supports_tools(args.model)
            )
            if not supports_tools:
                raise ValueError("Selected local model does not advertise tool calling; Citeproof requires repository-tool use.")
            profile = ollama_profile(args.model)

            def local_investigator(*call_args, **call_kwargs):
                call_kwargs["inference_profile"] = profile
                return investigate(*call_args, **call_kwargs)

            local_investigator.__name__ = "local_investigator"
            model_id = profile.model_id
            provider = profile.provider
            investigator = local_investigator
            verifier = None
            parallel_pair = False
            model_settings = _local_model_settings(profile)

        max_completions = args.max_completions or (
            profile.max_completions if args.provider == "ollama" else MAX_COMPLETIONS_PER_AGENT
        )
        output_path = args.output or default_output_path(project_root, args.case, model_id)
        output_path = output_path.resolve()
        if output_path.exists():
            raise ValueError(f"Refusing to overwrite existing report: {output_path}")

        code, report = benchmark_runner(
            repo_path,
            issue_path,
            gold_path,
            output_path,
            on_progress=lambda message: print(message, flush=True),
            investigator=investigator,
            model_id=model_id,
            provider=provider,
            verifier=verifier,
            parallel_pair=parallel_pair,
            pair_max_completions=max_completions,
            model_settings=model_settings,
        )
    except (OSError, ValueError) as exc:
        print(f"Benchmark could not run: {exc}", file=sys.stderr)
        return 2

    print(
        f"{report.get('status', 'unknown')}: provider={provider}, model={model_id}, "
        f"pair={report.get('pair', {}).get('model_requests', 'unknown')} requests, "
        f"baseline={report.get('baseline', {}).get('model_requests', 'unknown')} requests, "
        f"budget_matched={report.get('budget_matched', False)}; report path: {output_path}"
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
