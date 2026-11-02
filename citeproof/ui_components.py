"""Small, escaped HTML and Markdown builders for checked evidence."""

import html
import re
from urllib.parse import quote

from .models import Citation, Finding

_INLINE_CODE = re.compile(r"`([^`\r\n]{1,120})`")
_IDENTIFIER = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+(?=[^\s])")


def _verdict(citation: Citation) -> tuple[str, str]:
    if citation.valid and citation.outcome == "corrected_unique_exact_quote":
        return "Corrected", "corrected"
    if citation.valid:
        return "Verified", "verified"
    return "Rejected", "rejected"


def evidence_panel_html(
    citation: Citation,
    source_lines: list[str] | None,
    *,
    window_start: int,
    total_lines: int | None,
) -> str:
    """Render one bounded citation panel; all source and model text is escaped."""
    label, state = _verdict(citation)
    path = html.escape(str(citation.path), quote=True)
    symbol = html.escape(str(citation.symbol or "no symbol"), quote=True)
    claimed_start = citation.claimed_start_line or citation.start_line
    claimed_end = citation.claimed_end_line or citation.end_line
    actual_start, actual_end = citation.effective_range

    detail = ""
    if label == "Corrected":
        detail = (
            '<p class="cp-evidence-range">Claimed lines: '
            f"{claimed_start}-{claimed_end} · actual lines: {actual_start}-{actual_end}</p>"
        )
    elif label == "Rejected":
        detail = (
            '<div class="cp-claimed-quote"><strong>Claimed quote</strong><pre>'
            f"{html.escape(str(citation.quote), quote=True)}</pre></div>"
        )

    if source_lines is None:
        source_markup = '<p class="cp-source-unavailable">Source file is unavailable in the current pinned checkout.</p>'
    else:
        rows = []
        for number, line in enumerate(source_lines, start=max(1, window_start)):
            is_cited = citation.valid and actual_start <= number <= actual_end
            row_state = " cp-source-line-cited" if is_cited else ""
            rows.append(
                f'<div class="cp-source-line{row_state}">'
                f'<span class="cp-source-number">{number}</span>'
                f'<code>{html.escape(str(line), quote=True)}</code></div>'
            )
        source_markup = (
            f'<div class="cp-source-code" aria-label="Source lines {window_start}–'
            f'{window_start + len(source_lines) - 1}">'
            + "".join(rows)
            + "</div>"
        )
        if label == "Rejected":
            source_markup = '<div class="cp-actual-source"><strong>Source at claimed lines</strong>' + source_markup + "</div>"

    reason = html.escape(str(citation.reason), quote=True)
    return (
        f'<article class="cp-evidence-panel cp-evidence-{state}">'
        '<header class="cp-evidence-header">'
        f'<div class="cp-evidence-location"><code>{path}</code><span>{symbol}</span></div>'
        f'<span class="cp-verdict cp-verdict-{state}" aria-label="{label}">'
        f'<span class="cp-verdict-shape" aria-hidden="true">●</span>{label}</span>'
        '</header>'
        f'{detail}{source_markup}'
        f'<p class="cp-evidence-reason">{reason}</p>'
        '</article>'
    )


def sentence_citation_anchors(finding: Finding) -> list[dict]:
    """Link only sentence identifiers that literally occur in verified source evidence."""
    sentences = [part.strip() for part in _SENTENCE_BREAK.split(finding.explanation.strip()) if part.strip()]
    results = []
    for sentence in sentences:
        identifiers = [match.group(1) for match in _INLINE_CODE.finditer(sentence)]
        citation_indices = []
        for index, citation in enumerate(finding.citations):
            if not citation.valid:
                continue
            source_identifiers = set(_IDENTIFIER.findall(citation.quote))
            symbol_names = {citation.symbol, citation.symbol.rsplit(".", 1)[-1]} if citation.symbol else set()
            if any(identifier in source_identifiers or identifier in symbol_names for identifier in identifiers):
                citation_indices.append(index)
        results.append({
            "sentence": sentence,
            "citation_indices": citation_indices,
            "status": "Direct citation anchor" if citation_indices else "No direct citation anchor",
        })
    return results


def _markdown_escape(value: object) -> str:
    text = str(value).replace("\r", " ").replace("\n", " ")
    return re.sub(r"([\\`*_{}\[\]<>()#+.!|~-])", r"\\\1", text)


def issue_comment_markdown(
    finding: Finding,
    repo_slug: str | None,
    pinned_commit: str | None,
) -> str:
    """Build paste-ready Markdown with source links only for valid pinned citations."""
    lines = [f"## {_markdown_escape(finding.claim)}", "", _markdown_escape(finding.explanation), ""]
    safe_repo = bool(repo_slug and re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo_slug))
    safe_commit = bool(pinned_commit and re.fullmatch(r"[0-9a-fA-F]{6,64}", pinned_commit))
    for citation in finding.citations:
        label, _ = _verdict(citation)
        path = citation.path.replace("\\", "/")
        segments = path.split("/")
        safe_path = bool(path and all(segment not in {"", ".", ".."} for segment in segments))
        start_line, end_line = citation.effective_range
        if citation.valid and safe_repo and safe_commit and safe_path:
            encoded_path = quote(path, safe="/")
            url = (
                f"https://github.com/{repo_slug}/blob/{pinned_commit}/{encoded_path}"
                f"#L{start_line}-L{end_line}"
            )
            lines.append(f"- {label}: [`{_markdown_escape(path)}:{start_line}-{end_line}`]({url})")
        elif citation.valid:
            lines.append(f"- {label}: `{_markdown_escape(path)}:{start_line}-{end_line}` · Pinned source link unavailable.")
        else:
            lines.append(
                f"- Rejected: `{_markdown_escape(path)}` · "
                f"{_markdown_escape(citation.reason or 'Quote did not pass source verification.')}"
            )
    lines.extend(("", "> Citation verification confirms source text and line location; it does not prove the diagnosis is correct."))
    return "\n".join(lines)
