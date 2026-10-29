from dataclasses import dataclass, field

DIAGNOSIS_REVIEW_STATES = {
    "not_reviewed",
    "supported",
    "partly_supported",
    "unsupported",
    "incorrect",
}
EVALUATION_SCHEMA_V3 = "citeproof-evaluation/v3"
FINDING_ORDER_RANKING_METHOD = "finding_order_descending_plausibility"
EVALUATION_SCHEMAS = {"citeproof-evaluation/v1", "citeproof-evaluation/v2", EVALUATION_SCHEMA_V3}


@dataclass
class Citation:
    path: str
    symbol: str
    start_line: int
    end_line: int
    quote: str
    valid: bool = False
    reason: str = "Not checked"
    outcome: str | None = None
    claimed_start_line: int | None = None
    claimed_end_line: int | None = None
    corrected_start_line: int | None = None
    corrected_end_line: int | None = None

    def __post_init__(self) -> None:
        if self.claimed_start_line is None:
            self.claimed_start_line = self.start_line
        if self.claimed_end_line is None:
            self.claimed_end_line = self.end_line

    @property
    def effective_range(self) -> tuple[int, int]:
        if self.corrected_start_line is not None and self.corrected_end_line is not None:
            return self.corrected_start_line, self.corrected_end_line
        return self.start_line, self.end_line


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
