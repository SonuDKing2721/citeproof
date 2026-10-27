import unittest

from citeproof.models import Citation
from citeproof.presentation import citation_quote_details


class CitationPresentationTests(unittest.TestCase):
    def test_keeps_rejected_model_quote_visible_with_clear_label(self):
        quote = "this line is not in the cited source"
        citation = Citation("src/module.py", "convert", 3, 3, quote, valid=False)

        label, displayed_quote = citation_quote_details(citation)

        self.assertEqual(label, "Rejected model quote")
        self.assertEqual(displayed_quote, quote)

    def test_labels_verified_source_quote(self):
        citation = Citation("src/module.py", "convert", 3, 3, "actual source", valid=True)

        label, displayed_quote = citation_quote_details(citation)

        self.assertEqual(label, "Verified source quote")
        self.assertEqual(displayed_quote, "actual source")


if __name__ == "__main__":
    unittest.main()
