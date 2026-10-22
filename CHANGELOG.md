# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [4.0.0] - 2026-10-22

### Changed

- The model disclosure is verb-first and names each model's reasoning effort: `<Job> with <model> (<effort>) in <tool> via <host>.`, for example `Implemented with Claude Opus 5.5 (xhigh) and reviewed with GPT-6 Pro (max) in Claude Code via T3 Code.` Jobs that share a model are joined by `and`, as in `Planned and implemented with ...`. `with` is now a separator word and `for` is free text. The line always ends with a period
- `model-attribution` takes `off`, `effort`, `tool` or `host`, default `host`. The `model` and `job` levels are removed and fail the run like any unknown value
- Every level requires an effort on every model except `Human`; write `effort unknown` when nothing states it. Old `Generated with <model> for <job> ...` lines carry no effort and fail at every level
- The README's `AGENTS.md` snippet also asks agents to amend agent `Co-authored-by` trailers out of their commits before pushing

## [3.1.0] - 2026-10-07

### Added

- GitHub Marketplace metadata: the listing name `Post No Bills Check` and a white `slash` icon on dark gray

### Changed

- The action's display name is `Post No Bills Check`, because a Marketplace name cannot match an existing GitHub organization. The repository, the `post-no-bills` log prefix, inputs, defaults, and rules are unchanged
- The README gives an `AGENTS.md` snippet so that agents write the model disclosure before CI runs

## [3.0.0] - 2026-10-05

### Changed

- `require-model-attribution` is replaced by `model-attribution`: `off`, `model`, `job`, `tool` or `host`, default `host`. The final attribution line uses a stricter grammar, where `for`, `in`, `and` and `via` separate the fields and cannot appear inside a name, and every model has a job or none does

## Before 3.0.0

Versions 1.0.0 to 2.2.0 were early releases and are no longer published. Their commits stay in the history of `main`. Before 2.2.0 the repository was `stickerdaniel/agent-guardrails`; `uses:` references to that name do not resolve.

[Unreleased]: https://github.com/stickerdaniel/post-no-bills/compare/v4.0.0...HEAD
[4.0.0]: https://github.com/stickerdaniel/post-no-bills/compare/v3.1.0...v4.0.0
[3.1.0]: https://github.com/stickerdaniel/post-no-bills/compare/v3.0.0...v3.1.0
[3.0.0]: https://github.com/stickerdaniel/post-no-bills/releases/tag/v3.0.0
