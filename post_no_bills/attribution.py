# Ported from scripts/check_pr_model_attribution.py in
# https://github.com/stickerdaniel/linkedin-mcp-server at commit
# 6e7344763bc3e8b99b95d5468b9edeea511be61e, where it was released under
# Apache-2.0. Daniel Sticker is its sole author and relicenses it here under
# the MIT License of this repository. The Macroscope handling is unchanged;
# reading the event moved to event.py.
"""Require model attribution as the final non-empty PR body line."""

from __future__ import annotations

import re


_PLACEHOLDER_RE = re.compile(r"<[^>]*>|\[[^]]*]")
# Lowercase whole words. Splitting uses the spaced form (` with `, ` and `,
# ` in `, ` via `). A name that merely contains one is still rejected: the
# parser does not guess which occurrence was meant as a separator.
_SEPARATOR_WORD = re.compile(r"\b(?:with|and|in|via)\b")
# A model that needs no effort.
_HUMAN = "Human"
# Macroscope writes its summary into the PR body after the author, between
# these two markers, and appends the pair at the end when it finds none. The
# block is the bot's text, not the author's, so it is dropped before the final
# line is read; an attribution inside it does not count. An author can write
# the markers too, which buys text after the attribution but never a missing
# one; the two cannot be told apart, and disclosure is what the check guards.
# Macroscope puts each marker on a line of its own. A marker quoted in the
# author's text or in Macroscope's summary sits inside backticks or a quote, so
# only whole-line markers count, and the match may not cross another start:
# neither kind of quote can stretch the block over the author's own lines.
_MACROSCOPE_START = (
    r"^" + re.escape("<!-- Macroscope's pull request summary starts here -->") + r"$"
)
_MACROSCOPE_BLOCK_RE = re.compile(
    _MACROSCOPE_START
    + r"(?:(?!"
    + _MACROSCOPE_START
    + r").)*?^"
    + re.escape("<!-- Macroscope's pull request summary ends here -->")
    + r"$",
    re.DOTALL | re.MULTILINE,
)

_PLACEHOLDER = "The last line still holds a placeholder"
_FIELD = (
    "A name contains a separator word (with, and, in, via) or an unpaired "
    "parenthesis, or a part is empty or contains no alphanumeric character"
)
_EFFORT_TEXT = "An effort contains no alphanumeric character, or a parenthesis"
_NO_MODEL = "The last line names no model"
_LAST_JOB = "A model has no job, or the last job has no model"
_PERIOD = "The last line needs a final period"
_NO_LINE = "The PR body has no last line"
_NO_EFFORT = 'A model has no effort; write "(effort unknown)" when nothing states it'
_NO_TOOL = "The last line names no tool"
_NO_HOST = "The last line names no host"

# What the annotation tells the author to write, each with its final period.
_FORMS = {
    "model": "<Job> with <model>.",
    "effort": "<Job> with <model> (<effort>).",
    "tool": "<Job> with <model> (<effort>) in <tool>.",
    "host": "<Job> with <model> (<effort>) in <tool> via <host>.",
}
_EXAMPLES = {
    "model": "Implemented with Claude Opus 5.5.",
    "effort": "Implemented with Claude Opus 5.5 (xhigh).",
    "tool": "Implemented with Claude Opus 5.5 (xhigh) in Claude Code.",
    "host": "Implemented with Claude Opus 5.5 (xhigh) in Claude Code via T3 Code.",
}
_SEVERAL = {
    "model": "Implemented with Claude Opus 5.5 and reviewed with GPT-6 Pro.",
    "effort": "Implemented with Claude Opus 5.5 (xhigh) and reviewed with GPT-6 Pro (max).",
    "tool": (
        "Implemented with Claude Opus 5.5 (xhigh) and reviewed with GPT-6 Pro (max) "
        "in Claude Code."
    ),
    "host": (
        "Implemented with Claude Opus 5.5 (xhigh) and reviewed with GPT-6 Pro (max) "
        "in Claude Code via T3 Code."
    ),
}

# (jobs, model, effort). Several jobs share one model; effort is None when the
# model has no trailing parenthesised group.
_Clause = tuple[tuple[str, ...], str, str | None]
# (clauses, tool, host). tool and host are None when the line names neither.
Parsed = tuple[tuple[_Clause, ...], str | None, str | None]


def _bad_field(value: str) -> bool:
    if not any(character.isalnum() for character in value):
        return True
    # An unpaired parenthesis means a separator split a group: `(max in fast mode)`.
    if value.count("(") != value.count(")"):
        return True
    return _SEPARATOR_WORD.search(value) is not None


def _message(reason: str, level: str) -> str:
    return (
        f"{reason}. End the PR body with a line in this form: {_FORMS[level]} "
        f"Example: {_EXAMPLES[level]} "
        f"Several models: {_SEVERAL[level]}"
    )


def _model(text: str) -> tuple[str, str | None] | str:
    """(model, effort) from the text after ` with `, or the reason it is invalid.

    A parenthesised group that ends the text is the effort: "GPT-6 Pro (max)".
    Any effort text counts, "effort unknown" too; the check wants it stated.
    """
    text = text.strip()
    model, effort = text, None
    if text.endswith(")") and " (" in text:
        model, _, effort = text[:-1].rpartition(" (")
        effort = effort.strip()
        if not any(character.isalnum() for character in effort) or set("()") & set(effort):
            return _EFFORT_TEXT
    model = model.strip()
    if _bad_field(model):
        return _FIELD
    return (model, effort)


def _clauses(text: str) -> tuple[_Clause, ...] | str:
    """The `<job> with <model>` clauses joined by ` and `, or the first reason
    they are invalid. A chunk without ` with ` is a job that shares the next
    clause's model: "Planned and implemented with Claude Opus 5.5 (max)".
    """
    if " with " not in text:
        return _NO_MODEL
    clauses: list[_Clause] = []
    jobs: list[str] = []
    for chunk in text.split(" and "):
        if chunk.count(" with ") > 1:
            return _FIELD
        job_text, with_at, model_text = chunk.partition(" with ")
        job = job_text.strip()
        if _bad_field(job):
            return _FIELD
        jobs.append(job)
        if not with_at:
            continue
        named = _model(model_text)
        if isinstance(named, str):
            return named
        model, effort = named
        clauses.append((tuple(jobs), model, effort))
        jobs = []
    # A trailing chunk without ` with ` has no model to share.
    if jobs:
        return _LAST_JOB
    return tuple(clauses)


def parse(line: str) -> Parsed | str:
    """The line's fields, or the first reason it is not a valid attribution.

    Level requirements are not decided here: a thin line is valid, and check()
    says when a level asks for more.
    """
    if _PLACEHOLDER_RE.search(line):
        return _PLACEHOLDER

    period = line.endswith(".")
    rest = line[:-1] if period else line
    # A second ` in ` is a separator inside a name, not "the tool starts at
    # the last one". ` via ` only introduces a host after ` in `.
    if rest.count(" in ") > 1 or (" via " in rest and " in " not in rest):
        return _FIELD

    clauses_text, in_at, suffix = rest.partition(" in ")
    tool = None
    host = None
    if in_at:
        if suffix.count(" via ") > 1:
            return _FIELD
        tool_text, via_at, host_text = suffix.partition(" via ")
        tool = tool_text.strip()
        if _bad_field(tool):
            return _FIELD
        if via_at:
            host = host_text.strip()
            if _bad_field(host):
                return _FIELD

    clauses = _clauses(clauses_text)
    if isinstance(clauses, str):
        return clauses
    if not period:
        return _PERIOD
    return (clauses, tool, host)


def _last_line(body: str | None) -> str | None:
    if not body:
        return None
    # A body edited on the web arrives with CRLF, which `$` does not match.
    text = _MACROSCOPE_BLOCK_RE.sub("", body.replace("\r\n", "\n"))
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else None


def check(body: str | None, level: str) -> str | None:
    """The one-line failure for level, or None when the body passes it.

    `off` checks nothing. The message names the first problem and never quotes
    the body. A valid line that is too thin for the level fails after the
    grammar, so a broken line is not reported as merely missing a host.
    """
    if level == "off":
        return None
    line = _last_line(body)
    if line is None:
        return _message(_NO_LINE, level)
    parsed = parse(line)
    if isinstance(parsed, str):
        return _message(parsed, level)
    clauses, tool, host = parsed
    if level in ("effort", "tool", "host") and any(
        effort is None and model != _HUMAN for _, model, effort in clauses
    ):
        return _message(_NO_EFFORT, level)
    if level in ("tool", "host") and tool is None:
        return _message(_NO_TOOL, level)
    if level == "host" and host is None:
        return _message(_NO_HOST, level)
    return None
