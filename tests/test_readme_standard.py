"""Guard policy/checklist wiring, not the meaning or readability of prose."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReadmeStandardContract(unittest.TestCase):
    def contains(self, needle, text):
        # Treat Markdown wrapping as presentation, and avoid dumping whole policies.
        self.assertTrue(needle in " ".join(text.split()), f"missing requirement: {needle}")

    def test_universal_standard_has_checklist_and_record(self):
        text = (ROOT / "README-STANDARD.md").read_text()
        for section in (
            "## Scope", "## Write for the reader", "## Review checklist",
            "## Human readability rating", "## Review record", "## Rollout",
        ):
            self.contains(section, text)
        for field in ("Reader and purpose:", "Readability rating (0–4):",
                      "Evidence and navigation:", "Result: ready / revise / unknown"):
            self.contains(field, text)

    def test_standard_is_reachable_from_session_and_review_entrypoints(self):
        for name in ("STANDARDS.md", "AGENTS.md", "README.md", "PORTFOLIO-READINESS.md"):
            with self.subTest(document=name):
                self.contains("README-STANDARD.md", (ROOT / name).read_text())

    def test_scorecard_uses_existing_weights_without_extra_points(self):
        text = (ROOT / "PORTFOLIO-READINESS.md").read_text()
        self.contains("Policy version: **2.0.0 candidate**", text)
        self.contains("| Documentation | 8 |", text)
        self.contains("| Review efficiency | 10 |", text)
        self.contains("no additional weighted category", text)
        self.contains("Documentation and review-efficiency ratings cannot exceed", text)

    def test_readability_floor_and_audit_fields_are_explicit(self):
        text = (ROOT / "PORTFOLIO-READINESS.md").read_text()
        self.contains("human readability each ≥3", text)
        self.contains("review efficiency each ≥3", text)
        self.contains("Human readability (0–4):", text)
        self.contains("README review result: ready / revise / unknown", text)

    def test_existing_scores_and_automatic_checks_are_not_misrepresented(self):
        policy = (ROOT / "PORTFOLIO-READINESS.md").read_text()
        standard = (ROOT / "README-STANDARD.md").read_text()
        self.contains("Existing v1 assessments retain their original scores", policy)
        self.contains("does not automatically judge human readability", standard)
        self.contains("An agent read is a diagnostic, not human usability research", standard)


if __name__ == "__main__":
    unittest.main()
