"""Compare independently checked evidence without asserting diagnosis correctness."""

from dataclasses import dataclass

from .models import AgentResult


@dataclass(frozen=True)
class EvidenceComparison:
    status: str
    summary: str
    shared_files: list[str]
    overlapping_ranges: list[tuple[str, int, int]]


def compare_evidence(results: list[AgentResult]) -> EvidenceComparison:
    if len(results) < 2:
        return EvidenceComparison(
            "needs_two_agents",
            "Two completed agent results are required for comparison.",
            [],
            [],
        )
    if any(result.error for result in results):
        return EvidenceComparison(
            "incomplete",
            "Comparison is incomplete because at least one agent did not finish.",
            [],
            [],
        )

    evidence: list[set[tuple[str, int, int]]] = []
    for result in results[:2]:
        citations = {
            (citation.path, citation.start_line, citation.end_line)
            for finding in result.findings
            for citation in finding.citations
            if citation.valid
        }
        evidence.append(citations)

    if not evidence[0] or not evidence[1]:
        return EvidenceComparison(
            "no_verified_citations",
            "One or both agents returned no citations that passed the source checker.",
            [],
            [],
        )

    files_a = {path for path, _, _ in evidence[0]}
    files_b = {path for path, _, _ in evidence[1]}
    shared_files = sorted(files_a & files_b)
    overlaps: set[tuple[str, int, int]] = set()
    for path_a, start_a, end_a in evidence[0]:
        for path_b, start_b, end_b in evidence[1]:
            if path_a == path_b:
                start, end = max(start_a, start_b), min(end_a, end_b)
                if start <= end:
                    overlaps.add((path_a, start, end))

    overlapping_ranges = sorted(overlaps)
    if overlapping_ranges:
        summary = "Both agents cited verified, overlapping source lines. This is evidence overlap, not proof that their diagnosis is correct."
        status = "overlapping_lines"
    elif shared_files:
        summary = "Both agents cited verified evidence in the same file, but their line ranges do not overlap. This does not establish diagnosis agreement."
        status = "same_file"
    else:
        summary = "The agents' verified citations point to different files; review both evidence sets."
        status = "different_files"

    return EvidenceComparison(status, summary, shared_files, overlapping_ranges)
