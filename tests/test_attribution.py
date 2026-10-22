# Ported from tests/test_pr_model_attribution.py in
# https://github.com/stickerdaniel/linkedin-mcp-server at commit
# 6e7344763bc3e8b99b95d5468b9edeea511be61e, where it was released under
# Apache-2.0. Daniel Sticker is its sole author and relicenses it here under
# the MIT License of this repository. The pytest parametrizations are subTest
# loops. The cases are rewritten for the verb-first grammar. The
# event-reading and workflow tests moved to test_event.py, test_entrypoint.py,
# and test_workflows.py.
from __future__ import annotations

import io
import unittest

from post_no_bills import attribution, rules
from post_no_bills.report import Reporter

from .support import ROOT, policy

_TEMPLATE = ROOT / ".github" / "pull_request_template.md"
_README = ROOT / "README.md"
_LEVELS = ("effort", "tool", "host")

_NO_LINE = "The PR body has no last line"
_PLACEHOLDER = "The last line still holds a placeholder"
_FIELD = (
    "A name contains a separator word (with, and, in, via) or an unpaired "
    "parenthesis, or a part is empty or contains no alphanumeric character"
)
_EFFORT_TEXT = "An effort contains no alphanumeric character, or a parenthesis"
_NO_MODEL = "The last line names no model"
_LAST_JOB = "A model has no job, or the last job has no model"
_PERIOD = "The last line needs a final period"
_NO_EFFORT = 'A model has no effort; write "(effort unknown)" when nothing states it'
_NO_TOOL = "The last line names no tool"
_NO_HOST = "The last line names no host"

# Shown after "in this form: ", including the sentence period.
_FORMS = {
    "effort": "<Job> with <model> (<effort>).",
    "tool": "<Job> with <model> (<effort>) in <tool>.",
    "host": "<Job> with <model> (<effort>) in <tool> via <host>.",
}

# (line, passes effort, passes tool, passes host). The grammar accepts every
# line; the levels decide whether it is detailed enough.
_ACCEPTED = (
    ("Implemented with Claude Opus 5.", False, False, False),
    ("Implemented with Claude Opus 5.5 (max) .", True, False, False),
    ("Implemented with Claude Opus 5.5 (max)  in Claude Code via T3 Code.", True, True, True),
    (
        "Implemented with Claude Opus 5.5 (max)  and reviewed with GPT-6 Pro (high) "
        "in Claude Code via T3 Code.",
        True,
        True,
        True,
    ),
    ("Implemented with Command R.", False, False, False),
    ("Implemented with GPT-5.6 Sol (high).", True, False, False),
    ("Implemented with Salesforce xGen (unknown) in T3 Code.", True, True, False),
    ("Implemented with Gemini 3 Pro Preview (low) in Gemini CLI via Zed.", True, True, True),
    ("Planned, implemented/tested with GPT-5.6 Sol (xhigh) in T3 Code.", True, True, False),
    ("Security review for CI with GPT-5.6 Sol (high) in T3 Code.", True, True, False),
    ("Implemented with Claude Opus 5.5 for speed (max) in Claude Code via T3 Code.", True, True, True),
    ("Planned and implemented and tested with Codex (medium) in Codex CLI via T3 Code.", True, True, True),
    (
        "Planned with Claude Opus 5.5 (max) and implemented and tested with Codex (medium) in T3 Code.",
        True,
        True,
        False,
    ),
    (
        "Implemented with Claude Sonnet 4.5 (high) and reviewed with GPT-5.6 (xhigh) and "
        "tested with Codex (low) in T3 Code.",
        True,
        True,
        False,
    ),
    ("Written with Human.", True, False, False),
    ("Written with Human in Zed via GitHub.", True, True, True),
    ("Written with Human and reviewed with GPT-6 Pro in Zed via GitHub.", False, False, False),
    ("Written with human in Zed via GitHub.", False, False, False),
    ("Implemented with Claude (beta) Opus (max).", True, False, False),
    ("Implemented with Claude Opus 5.5 ( max ).", True, False, False),
    ("Implemented with Claude Opus 5.5(max).", False, False, False),
    ("Implemented with Claude Opus 5.5 (max) preview.", False, False, False),
    ("Implemented with GPT-5.6 in Claude Code via T3 Code.", False, False, False),
)

# Bodies as well as lines: check() reads the last line.
_REJECTED = (
    "## Summary\n\nNo attribution here.",
    "Implemented with GPT-5.6 (high) in Claude Code.\n\nA later non-empty line.",
    "Done.",
    "Implemented in Claude Code via T3 Code.",
    "Implemented With Claude Opus 5.5 (max).",
    "Implemented with Claude Opus 5.5 (max in fast mode).",
    "Implemented (mostly with Claude Opus 5.5 (max).",
    "Implemented with Claude )beta( (max) in Claude Code via T3 Code.",
    "Implemented with Claude Opus 5.5 (max) in )Claude( Code via T3 Code.",
    "Implemented )now( with Claude Opus 5.5 (max) in Claude Code via T3 Code.",
    "Implemented with GPT-5.6 (high) via T3 Code.",
    "Implemented with GPT-5.6",
    "Implemented with GPT-5.6 (high)",
    "Implemented with GPT-5.6 (high) in Claude Code",
    "Implemented with GPT-5.6 (high) in via T3 Code.",
    "Implemented with GPT-5.6 (high) in Claude Code via .",
    "Implemented with GPT-5.6 (high) in Claude Code via T3 Code via another wrapper.",
    "Implemented with GPT-5.6 (high) in Claude Code in a Box.",
    "Implemented with GPT-5.6 (high) in Claude Code and GPT-6 Pro.",
    "Implemented with GPT-5.6 (high) in -.",
    "Implemented with GPT-5.6 (high) in Claude Code via ---.",
    ".",
    "..",
    "Implemented with .",
    "/ with Claude Opus 5.5 (max).",
    "Implemented with GPT-5.6 and-Research (max).",
    "<Job> with <model>.",
    "[job] with [model] ([effort]) in [tool] via [host].",
    "Implemented with Claude Opus 5.5 (xhigh) and GPT-6 Pro (max) in Claude Code via T3 Code.",
    "Implemented with Claude Opus 5.5 (xhigh) and reviewed.",
    "Implemented with Claude Opus 5.5 (xhigh) and  with GPT-6 Pro (max).",
    "Implemented with Claude Opus 5.5 with GPT-6 Pro (max).",
    "Planned and implemented with Claude with Codex (max).",
    "Implemented with Claude Opus 5.5 ().",
    "Implemented with Claude Opus 5.5 ( ).",
    "Implemented with Claude Opus 5.5 (-).",
    "Implemented with Claude Opus 5.5 (a (b)).",
    "Implemented with Claude Opus 5.5 (max)) in Claude Code.",
    "",
    None,
)


def _passes(body: str | None, level: str) -> bool:
    return attribution.check(body, level) is None


def _template_line() -> str:
    lines = [
        line.strip()
        for line in _TEMPLATE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return lines[-1]


def _readme_table() -> tuple[list[str], list[list[str]]]:
    """(level columns, rows of cells) of the table under the README's
    "Model attribution" details."""
    text = _README.read_text(encoding="utf-8")
    section = text.split("<summary><strong>Model attribution</strong></summary>", 1)[1]
    section = section.split("</details>", 1)[0]
    rows = [
        [cell.strip() for cell in line.strip().strip("|").split("|")]
        for line in section.splitlines()
        if line.lstrip().startswith("|")
    ]
    header, delimiter, *data = rows
    # Without its delimiter row the Markdown is no table, and the first
    # example would be read as one.
    if not all(set(cell) <= set(":-") and "-" in cell for cell in delimiter):
        raise AssertionError(f"README table has no delimiter row: {delimiter}")
    return [cell.strip("`") for cell in header[1:]], data


class ReadmeTableTests(unittest.TestCase):
    def test_every_row_at_every_level(self) -> None:
        levels, rows = _readme_table()
        self.assertEqual(tuple(levels), _LEVELS)
        self.assertTrue(rows)
        for line, *cells in rows:
            line = line.strip("`")
            for level, cell in zip(levels, cells, strict=True):
                with self.subTest(line=line, level=level):
                    self.assertIn(cell, ("✓", "✗"))
                    self.assertEqual(_passes(line, level), cell == "✓")


class AttributionGrammarTests(unittest.TestCase):
    def test_accepted_lines_pass_the_levels_they_satisfy(self) -> None:
        for line, *expected in _ACCEPTED:
            with self.subTest(line=line):
                self.assertNotIsInstance(attribution.parse(line), str)
            for level, ok in zip(_LEVELS, expected, strict=True):
                with self.subTest(line=line, level=level):
                    self.assertEqual(_passes(line, level), ok)

    def test_rejected_lines_fail_at_every_level(self) -> None:
        for body in _REJECTED:
            for level in _LEVELS:
                with self.subTest(body=body, level=level):
                    self.assertFalse(_passes(body, level))

    def test_dangling_separators_are_rejected(self) -> None:
        for keyword in ("with", "and", "in", "via"):
            for line in (
                f"Implemented with GPT-5.6 (high) {keyword}",
                f"Implemented with GPT-5.6 (high) {keyword}.",
                f"{keyword} Implemented with GPT-5.6 (high).",
            ):
                for level in _LEVELS:
                    with self.subTest(line=line, level=level):
                        self.assertFalse(_passes(line, level))

    def test_accepts_trailing_blank_lines(self) -> None:
        body = "## Summary\n\nDone.\n\nImplemented with GPT-5.6 (high) in Claude Code.\n\n"
        self.assertTrue(_passes(body, "tool"))
        self.assertFalse(_passes(body, "host"))

    def test_parse_reads_the_fields(self) -> None:
        self.assertEqual(
            attribution.parse(
                "Security review for CI with Claude Opus 5.5 for speed (effort unknown) "
                "and reviewed with GPT-6 Pro (max) in Claude Code via T3 Code."
            ),
            (
                (
                    (("Security review for CI",), "Claude Opus 5.5 for speed", "effort unknown"),
                    (("reviewed",), "GPT-6 Pro", "max"),
                ),
                "Claude Code",
                "T3 Code",
            ),
        )
        self.assertEqual(
            attribution.parse(
                "Planned and implemented with Claude Opus 5.5 (max) and reviewed with Human."
            ),
            (
                (
                    (("Planned", "implemented"), "Claude Opus 5.5", "max"),
                    (("reviewed",), "Human", None),
                ),
                None,
                None,
            ),
        )
        self.assertEqual(
            attribution.parse("Implemented with Claude (beta) Opus (max) in T3 Code."),
            (((("Implemented",), "Claude (beta) Opus", "max"),), "T3 Code", None),
        )

    def test_documented_limits(self) -> None:
        # A separator word inside the effort splits the line like anywhere else,
        # which leaves an unpaired parenthesis on each side.
        self.assertEqual(
            attribution.parse("Implemented with Claude Opus 5.5 (work in progress)."), _FIELD
        )
        self.assertEqual(
            attribution.parse("Research and development with Claude Opus 5.5 (max)."),
            (((("Research", "development"), "Claude Opus 5.5", "max"),), None, None),
        )
        self.assertEqual(
            attribution.parse("Implemented with Claude Opus 5.5 (max) in Claude Code & GPT-6 Pro."),
            (((("Implemented",), "Claude Opus 5.5", "max"),), "Claude Code & GPT-6 Pro", None),
        )
        self.assertEqual(
            attribution.parse("Implemented with Claude Opus 5.5 (max) in Claude Code AND GPT-6 Pro."),
            (((("Implemented",), "Claude Opus 5.5", "max"),), "Claude Code AND GPT-6 Pro", None),
        )

    def test_parse_returns_a_line_reason(self) -> None:
        cases = (
            ("Done.", _NO_MODEL),
            ("[job] with [model].", _PLACEHOLDER),
            ("Implemented with GPT-5.6 and", _FIELD),
            ("and Implemented with GPT-5.6.", _FIELD),
            ("Implemented with GPT-5.6 and.", _FIELD),
            ("Implemented with Claude with GPT-5.6 (max).", _FIELD),
            ("Implemented with GPT-5.6 ().", _EFFORT_TEXT),
            ("Implemented with GPT-5.6 (a (b)).", _EFFORT_TEXT),
            ("Implemented with Claude Opus 5.5 (max) and GPT-6 Pro (max).", _LAST_JOB),
            ("Implemented with Claude Opus 5.5 (max) and reviewed.", _LAST_JOB),
            ("Implemented with Claude Opus 5.5 (max)", _PERIOD),
        )
        for line, reason in cases:
            with self.subTest(line=line):
                self.assertEqual(attribution.parse(line), reason)


class ReasonTests(unittest.TestCase):
    def test_each_reason_leads_the_message(self) -> None:
        cases = (
            ("effort", None, _NO_LINE),
            ("effort", "Done.", _NO_MODEL),
            ("effort", "[job] with [model].", _PLACEHOLDER),
            ("effort", "Implemented with GPT-5.6 and", _FIELD),
            ("effort", "Implemented with GPT-5.6 ().", _EFFORT_TEXT),
            ("effort", "Implemented with Claude Opus 5.5 (max) and GPT-6 Pro (max).", _LAST_JOB),
            ("effort", "Implemented with Claude Opus 5.5", _PERIOD),
            ("effort", "Implemented with Claude Opus 5.5.", _NO_EFFORT),
            (
                "host",
                "Generated with Claude Opus 5.5 for implementation in Claude Code via T3 Code.",
                _NO_EFFORT,
            ),
            ("tool", "Implemented with Claude Opus 5.5 (max).", _NO_TOOL),
            ("host", "Implemented with Claude Opus 5.5 (max) in Claude Code.", _NO_HOST),
        )
        for level, body, reason in cases:
            with self.subTest(body=body, level=level):
                message = attribution.check(body, level)
                self.assertTrue(message.startswith(reason + "."), message)
                self.assertNotIn("\n", message)
                self.assertNotIn("..", message)

    def test_an_earlier_reason_wins(self) -> None:
        cases = (
            ("effort", "\n\n", _NO_LINE, _NO_MODEL),
            ("effort", "See [model]", _PLACEHOLDER, _NO_MODEL),
            (
                "effort",
                "[job] with Claude Opus 5.5 (max) and GPT-6 Pro in Code in a Box.",
                _PLACEHOLDER,
                _FIELD,
            ),
            (
                "effort",
                "Implemented with Claude Opus 5.5 (max) and  with GPT-6 Pro (max)",
                _FIELD,
                _PERIOD,
            ),
            ("effort", "Implemented with Claude Opus 5.5 ()", _EFFORT_TEXT, _PERIOD),
            (
                "effort",
                "Implemented with Claude Opus 5.5 (max) and GPT-6 Pro (max)",
                _LAST_JOB,
                _PERIOD,
            ),
            (
                "effort",
                "Implemented with Claude Opus 5.5 (max) and GPT-6 Pro in Claude Code.",
                _LAST_JOB,
                _NO_EFFORT,
            ),
            ("effort", "Implemented with Claude Opus 5.5 in Claude Code", _PERIOD, _NO_EFFORT),
            ("host", "Implemented with Claude Opus 5.5 (max) via T3 Code.", _FIELD, _NO_TOOL),
            ("tool", "Implemented with Claude Opus 5.5.", _NO_EFFORT, _NO_TOOL),
            ("host", "Implemented with Claude Opus 5.5 (max).", _NO_TOOL, _NO_HOST),
        )
        for level, body, earlier, later in cases:
            with self.subTest(body=body, level=level):
                message = attribution.check(body, level)
                self.assertTrue(message.startswith(earlier + "."), message)
                self.assertFalse(message.startswith(later + "."), message)

    def test_each_message_example_passes_its_level(self) -> None:
        for level in _LEVELS:
            message = attribution.check(None, level)
            with self.subTest(level=level):
                self.assertNotIn("\n", message)
                self.assertNotIn("..", message)
                form = message.split("in this form: ", 1)[1].split(" Example: ", 1)[0]
                example, several = message.split("Example: ", 1)[1].split(" Several models: ", 1)
                self.assertEqual(form, _FORMS[level])
                self.assertIsNone(attribution.check(example, level))
                self.assertIsNone(attribution.check(several, level))

    def test_the_message_does_not_quote_the_body(self) -> None:
        body = "zebra-marker is not an attribution"
        for level in _LEVELS:
            with self.subTest(level=level):
                self.assertNotIn("zebra-marker", attribution.check(body, level))


#: Macroscope's block as it lands in a PR body, trimmed from linkedin-mcp-server#1132.
_MACROSCOPE = (
    "<!-- Macroscope's pull request summary starts here -->\n"
    "<!-- Macroscope will only edit the content between these invisible "
    "markers, and the markers themselves will not be visible in the GitHub "
    "rendered markdown. -->\n"
    "> [!NOTE]\n"
    "> ### Exempt Renovate PRs from the changelog fragment requirement\n"
    "> <!-- Macroscope's review summary starts here -->\n"
    "> <sup>Macroscope summarized de6f451.</sup>\n"
    "> <!-- Macroscope's review summary ends here -->\n"
    ">\n"
    "<!-- Macroscope's pull request summary ends here -->\n"
)
_LINE = "Implemented with Claude Opus 5.5 (xhigh)."


class MacroscopeTests(unittest.TestCase):
    def test_ignores_the_macroscope_summary(self) -> None:
        bodies = {
            "summary-after": f"## Summary\n\nDone.\n\n{_LINE}\n\n{_MACROSCOPE}",
            "summary-before": f"## Summary\n\nDone.\n\n{_MACROSCOPE}\n{_LINE}\n",
            "marker-quoted-above": (
                "Macroscope opens with `<!-- Macroscope's pull request summary "
                f"starts here -->`.\n\n{_LINE}\n\n{_MACROSCOPE}"
            ),
            "marker-line-in-code-block": (
                "The block starts with:\n\n```\n"
                "<!-- Macroscope's pull request summary starts here -->\n```\n\n"
                f"{_LINE}\n\n{_MACROSCOPE}"
            ),
            "marker-quoted-inside": (
                f"## Summary\n\nDone.\n\n{_LINE}\n\n"
                + _MACROSCOPE.replace(
                    "> [!NOTE]\n",
                    "> [!NOTE]\n> It skips `<!-- Macroscope's pull request summary "
                    "starts here -->` blocks.\n",
                )
            ),
        }
        for name, body in bodies.items():
            for newline_name, newline in (("lf", "\n"), ("crlf", "\r\n")):
                with self.subTest(body=name, newline=newline_name):
                    self.assertTrue(_passes(body.replace("\n", newline), "effort"))

    def test_the_macroscope_summary_carries_no_attribution(self) -> None:
        bodies = {
            "only-inside-the-summary": (
                f"## Summary\n\nDone.\n\n{_MACROSCOPE.replace('> [!NOTE]', _LINE)}"
            ),
            # Without its end marker the text is not Macroscope's block.
            "unterminated": (
                f"{_LINE}\n\n<!-- Macroscope's pull request summary starts here -->\nx"
            ),
        }
        for name, body in bodies.items():
            with self.subTest(body=name):
                self.assertFalse(_passes(body, "effort"))


class TemplateTests(unittest.TestCase):
    def test_no_body_and_the_template_line_fail_every_level(self) -> None:
        for body in (None, _template_line()):
            for level in _LEVELS:
                with self.subTest(body=body, level=level):
                    self.assertFalse(_passes(body, level))

    def test_template_ends_with_editable_attribution_placeholder(self) -> None:
        lines = [
            line.strip()
            for line in _TEMPLATE.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

        self.assertEqual(lines[-1], "[job] with [model] ([effort]) in [tool] via [host].")
        self.assertIn("default level is host", lines[-2])
        self.assertIn("ends with a period", lines[-2])
        self.assertIn("in Claude Code via T3 Code", lines[-2])
        self.assertEqual(attribution.parse(lines[-1]), _PLACEHOLDER)


class AnnotationTests(unittest.TestCase):
    def test_failure_emits_actionable_github_annotation(self) -> None:
        stream = io.StringIO()
        findings = rules.check_attribution("No attribution", "jane", policy({"model-attribution": "effort"}))
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].title, "PR model attribution required")
        self.assertEqual(findings[0].message, attribution.check("No attribution", "effort"))
        self.assertNotIn("\n", findings[0].message)
        for finding in findings:
            Reporter(stream).finding(finding)

        output = stream.getvalue()
        self.assertTrue(output.startswith("::error title=PR model attribution required::"))
        self.assertNotIn("%0A", output.splitlines()[0])
        self.assertIn(_NO_MODEL, output)
        self.assertIn("<Job> with <model> (<effort>).", output)
        self.assertIn("Implemented with Claude Opus 5.5 (xhigh).", output)


if __name__ == "__main__":
    unittest.main()
