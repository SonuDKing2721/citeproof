from dataclasses import dataclass, field


@dataclass
class Citation:
    path: str
    symbol: str
    start_line: int
    end_line: int
    quote: str
    valid: bool = False
    reason: str = "Not checked"


@dataclass
class Finding:
    claim: str
    explanation: str
    citations: list[Citation] = field(default_factory=list)


@dataclass
class AgentResult:
    agent_name: str
    findings: list[Finding]
    trace: list[str]
    error: str | None = None
    model_requests: int = 0
    model_requests_known: bool = True


@dataclass
class VerificationReview:
    """Bounded model review over findings and citations already checked by Citeproof."""

    status: str
    assessment: str = "not_run"
    selected_finding_id: str | None = None
    supporting_evidence_ids: list[str] = field(default_factory=list)
    challenging_evidence_ids: list[str] = field(default_factory=list)
    rationale: str = ""
    test_scenario: str | None = None
    test_assertion: str | None = None
    model_requests: int = 0
    error: str | None = None
