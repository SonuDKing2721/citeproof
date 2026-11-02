"""Blinded, append-only human review of saved pair-versus-baseline reports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import secrets
import tempfile
from typing import Any


SCHEMA = "citeproof-blind-review/v1"
COMPARISON_SCHEMAS = {"citeproof-budget-comparison/v1", "citeproof-budget-comparison/v2"}
REVIEW_LABELS = {"A stronger", "B stronger", "Tie", "Neither useful", "Unable to judge"}
MAX_NOTE_CHARS = 1200


@dataclass(frozen=True)
class BlindReviewSession:
    identity: str
    option_a: dict[str, Any]
    option_b: dict[str, Any]
    saved_label: str | None
    note: str
    mapping_revealed: dict[str, str] | None


def list_reviewable_reports(directory: str | Path) -> list[tuple[Path, dict[str, Any]]]:
    """Read saved comparison reports that contain both pair and baseline data."""
    root = Path(directory)
    reports: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(root.glob("*comparison*.json")):
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Could not read comparison report {path.name}: {exc}") from exc
        if not isinstance(report, dict) or report.get("schema") not in COMPARISON_SCHEMAS:
            continue
        if isinstance(report.get("pair"), dict) and isinstance(report.get("baseline"), dict):
            reports.append((path, report))
    return reports


def _report_identity(report: dict[str, Any]) -> str:
    canonical = json.dumps(report, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _empty_store() -> dict[str, Any]:
    return {"schema": SCHEMA, "reviews": {}}


def _load_store(path: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise ValueError("Blind-review annotation path must not be a symbolic link.")
    if not path.exists():
        return _empty_store()
    try:
        store = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read blind-review annotations: {exc}") from exc
    if not isinstance(store, dict) or store.get("schema") != SCHEMA or not isinstance(store.get("reviews"), dict):
        raise ValueError("Blind-review annotation file has an unsupported format.")
    return store


def _write_store(path: Path, store: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError("Blind-review annotation path must not be a symbolic link.")
    serialized = json.dumps(store, ensure_ascii=False, indent=2) + "\n"
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(serialized)
            temporary_path = Path(temporary.name)
        temporary_path.replace(path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def _field_text(value: object, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:limit]


def _side_summary(source: dict[str, Any]) -> dict[str, Any]:
    localization = source.get("localization")
    localization = localization if isinstance(localization, dict) else {}
    ranked = localization.get("ranked_files")
    if not isinstance(ranked, list):
        ranked = []
    hit = localization.get("primary_hit_at_1")
    if not isinstance(hit, bool):
        hit = None
    recall = localization.get("gold_file_recall_at_3")
    if isinstance(recall, bool) or not isinstance(recall, (int, float)) or not 0 <= recall <= 1:
        recall = None

    agents = source.get("agents")
    normalized_findings: list[dict[str, Any]] = []
    if isinstance(agents, list):
        for agent in agents[:4]:
            if not isinstance(agent, dict):
                continue
            findings = agent.get("findings")
            if not isinstance(findings, list):
                continue
            for finding in findings[:8]:
                if not isinstance(finding, dict):
                    continue
                citations = finding.get("citations")
                normalized_citations = []
                if isinstance(citations, list):
                    for citation in citations[:8]:
                        if not isinstance(citation, dict):
                            continue
                        normalized_citations.append({
                            "path": _field_text(citation.get("path"), 300),
                            "symbol": _field_text(citation.get("symbol"), 160),
                            "start_line": citation.get("start_line") if isinstance(citation.get("start_line"), int) else None,
                            "end_line": citation.get("end_line") if isinstance(citation.get("end_line"), int) else None,
                            "quote": _field_text(citation.get("quote"), 2000),
                            "valid": citation.get("valid") if isinstance(citation.get("valid"), bool) else None,
                        })
                normalized_findings.append({
                    "claim": _field_text(finding.get("claim"), 600),
                    "explanation": _field_text(finding.get("explanation"), 1400),
                    "citations": normalized_citations,
                })
                if len(normalized_findings) >= 12:
                    break
            if len(normalized_findings) >= 12:
                break

    return {
        "model_requests": source.get("model_requests") if isinstance(source.get("model_requests"), int) else None,
        "localization_status": _field_text(localization.get("status"), 40) or "unknown",
        "ranked_files": [_field_text(item, 300) for item in ranked[:10] if isinstance(item, str)],
        "primary_hit_at_1": hit,
        "gold_file_recall_at_3": float(recall) if recall is not None else None,
        "findings": normalized_findings,
    }


def _new_review_entry() -> dict[str, Any]:
    return {
        "order": secrets.choice([["pair", "baseline"], ["baseline", "pair"]]),
        "label": None,
        "note": "",
        "saved_at_utc": None,
    }


def _session(report: dict[str, Any], identity: str, entry: dict[str, Any]) -> BlindReviewSession:
    order = entry.get("order")
    if order not in (["pair", "baseline"], ["baseline", "pair"]):
        raise ValueError("Blind-review option order is invalid.")
    source_by_key = {"pair": report["pair"], "baseline": report["baseline"]}
    saved_label = entry.get("label") if entry.get("label") in REVIEW_LABELS else None
    note = _field_text(entry.get("note"), MAX_NOTE_CHARS)
    reveal = None
    if saved_label is not None and note:
        reveal = {
            "A": "Two-agent pair" if order[0] == "pair" else "Single-agent baseline",
            "B": "Single-agent baseline" if order[1] == "baseline" else "Two-agent pair",
        }
    return BlindReviewSession(
        identity=identity,
        option_a=_side_summary(source_by_key[order[0]]),
        option_b=_side_summary(source_by_key[order[1]]),
        saved_label=saved_label,
        note=note,
        mapping_revealed=reveal,
    )


def begin_blind_review(report: dict[str, Any], annotation_path: str | Path) -> BlindReviewSession:
    """Create and persist a hidden A/B order, or reopen an existing review."""
    if not isinstance(report, dict) or report.get("schema") not in COMPARISON_SCHEMAS:
        raise ValueError("Blind review requires a supported pair-versus-baseline report.")
    if not isinstance(report.get("pair"), dict) or not isinstance(report.get("baseline"), dict):
        raise ValueError("Blind review requires both pair and baseline results.")
    path = Path(annotation_path)
    identity = _report_identity(report)
    store = _load_store(path)
    reviews = store["reviews"]
    entry = reviews.get(identity)
    if entry is None:
        entry = _new_review_entry()
        reviews[identity] = entry
        _write_store(path, store)
    if not isinstance(entry, dict):
        raise ValueError("Blind-review annotation entry is invalid.")
    return _session(report, identity, entry)


def save_blind_review(
    report: dict[str, Any],
    annotation_path: str | Path,
    label: str,
    note: str,
) -> BlindReviewSession:
    """Append one blinded label and note; never overwrite a completed review."""
    normalized_label = _field_text(label, 40)
    normalized_note = _field_text(note, MAX_NOTE_CHARS)
    if normalized_label not in REVIEW_LABELS:
        raise ValueError("Choose a valid blind-review label.")
    if not normalized_note:
        raise ValueError("Add a brief note before saving the blind review.")
    if len(note) > MAX_NOTE_CHARS:
        normalized_note = normalized_note[:MAX_NOTE_CHARS]

    path = Path(annotation_path)
    identity = _report_identity(report)
    store = _load_store(path)
    reviews = store["reviews"]
    entry = reviews.get(identity)
    if entry is None:
        entry = _new_review_entry()
        reviews[identity] = entry
    if not isinstance(entry, dict):
        raise ValueError("Blind-review annotation entry is invalid.")
    if entry.get("label") in REVIEW_LABELS and _field_text(entry.get("note"), MAX_NOTE_CHARS):
        raise ValueError("A blind review is already saved; existing labels are preserved.")
    entry["label"] = normalized_label
    entry["note"] = normalized_note
    entry["saved_at_utc"] = datetime.now(timezone.utc).isoformat()
    _write_store(path, store)
    return _session(report, identity, entry)
