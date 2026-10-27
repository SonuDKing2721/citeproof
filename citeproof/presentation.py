"""Small presentation helpers for clear citation states."""

from .models import Citation


def citation_quote_details(citation: Citation) -> tuple[str, str]:
    label = "Verified source quote" if citation.valid else "Rejected model quote"
    return label, citation.quote
