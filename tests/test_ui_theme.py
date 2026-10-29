import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STYLESHEET = PROJECT_ROOT / "assets" / "citeproof.css"


def _tokens(stylesheet: str) -> dict[str, str]:
    return dict(re.findall(r"(--cp-[\w-]+)\s*:\s*(#[0-9a-fA-F]{6})\s*;", stylesheet))


def _luminance(hex_color: str) -> float:
    channels = [int(hex_color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4 for channel in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(first: str, second: str) -> float:
    high, low = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


class UIThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not STYLESHEET.is_file():
            raise AssertionError(f"Missing editorial stylesheet: {STYLESHEET}")
        cls.stylesheet = STYLESHEET.read_text(encoding="utf-8")
        cls.colors = _tokens(cls.stylesheet)

    def test_editorial_text_colors_meet_wcag_aa_contrast(self):
        required = {"--cp-paper", "--cp-ink", "--cp-muted", "--cp-forest", "--cp-on-forest"}
        self.assertTrue(required.issubset(self.colors), f"Missing palette tokens: {sorted(required - self.colors.keys())}")
        self.assertGreaterEqual(_contrast(self.colors["--cp-ink"], self.colors["--cp-paper"]), 4.5)
        self.assertGreaterEqual(_contrast(self.colors["--cp-muted"], self.colors["--cp-paper"]), 4.5)
        self.assertGreaterEqual(_contrast(self.colors["--cp-on-forest"], self.colors["--cp-forest"]), 4.5)

    def test_theme_has_keyboard_focus_and_narrow_layout_rules(self):
        self.assertIn(":focus-visible", self.stylesheet)
        self.assertRegex(self.stylesheet, r"@media\s*\(max-width:\s*\d+px\)")

    def test_toolbar_keeps_sidebar_navigation_available_without_deploy_button(self):
        self.assertNotRegex(
            self.stylesheet,
            r'\[data-testid="stToolbar"\]\s*\{[^}]*visibility\s*:\s*hidden',
        )
        self.assertRegex(
            self.stylesheet,
            r'\[data-testid="stAppDeployButton"\]\s*\{[^}]*display\s*:\s*none',
        )

    def test_sticky_header_has_opaque_canvas_background(self):
        header_rule = re.search(r'\[data-testid="stHeader"\]\s*\{([^}]*)\}', self.stylesheet)
        self.assertIsNotNone(header_rule)
        self.assertIn("background: var(--cp-canvas);", header_rule.group(1))

    def test_theme_has_no_remote_font_dependency_or_global_transition(self):
        self.assertNotRegex(self.stylesheet, r"(?i)@import\s+url\(")
        self.assertNotRegex(self.stylesheet, r"(?i)transition\s*:\s*all\b")


if __name__ == "__main__":
    unittest.main()
