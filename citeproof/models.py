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
