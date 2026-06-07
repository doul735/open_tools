# open_tools

[![CI](https://github.com/doul735/open_tools/actions/workflows/ci.yml/badge.svg)](https://github.com/doul735/open_tools/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Open-source agent tools that keep LLMs useful without letting them invent operational facts.

This repository is the home for the `open_*` series. Stars, issues, discussions, and project-level documentation live here; each tool is still packaged and released independently so users can install only what they need.

## What This Is

`open_*` tools are small CLIs and agent skills for jobs where an LLM should help parse intent, but should not invent the final answer. Each package keeps a specific external data source as the source of truth and makes that boundary visible in the output.

The first package is `open-gil`, a public-transit departure planner for Seoul, Gyeonggi, and Incheon. It lets an agent turn a Korean natural-language route question into structured input, then uses APIs for place lookup and route calculation.

## Packages

| Package | CLI | Status | Purpose |
| --- | --- | --- | --- |
| [`open-gil`](packages/open-gil) | `open-gil` | MVP | TMAP-backed public-transit departure planning for Seoul, Gyeonggi, and Incheon. |
| `open-review` | `open-review` | Planned | Review workflows for code, docs, and release checks. |

## Current State

`open-gil` is the current MVP.

- Route calculation source of truth: TMAP Transit API
- Coordinate fallback: Kakao Local API, optional and used only for coordinate lookup
- Agent surfaces: Codex repo skill in `.agents/skills/open-gil`, package skill in `packages/open-gil/skills/open-gil`
- Output contract: stable JSON envelope plus human-readable Korean route summaries
- Hard guardrail: one TMAP Transit route calculation per natural-language request
- Release status: `open-gil` is published on PyPI

For the design history, tradeoffs, and next steps, see [Open Gil Development Story](docs/open-gil-development-story.md).

## Install

```bash
pipx install open-gil
```

If `pipx` is unavailable, use a persistent venv instead of `/tmp`:

```bash
python3 -m venv "$HOME/.local/share/open-gil/venv"
"$HOME/.local/share/open-gil/venv/bin/python" -m pip install --upgrade pip
"$HOME/.local/share/open-gil/venv/bin/python" -m pip install --upgrade "open-gil>=0.1.4"
"$HOME/.local/share/open-gil/venv/bin/open-gil" --version
```

You can also install `open-gil` directly from this repository:

```bash
pipx install "git+https://github.com/doul735/open_tools.git#subdirectory=packages/open-gil"
```

Developers can work from the monorepo.

```bash
git clone https://github.com/doul735/open_tools.git
cd open_tools
python -m venv .venv
. .venv/bin/activate
python -m pip install -e "./packages/open-gil[dev]"
```

## Repository Layout

```text
packages/
  open-gil/
    pyproject.toml
    src/open_gil/
    tests/
    skills/open-gil/
.agents/
  skills/open-gil/
docs/
```

The root `.agents/skills` directory is for Codex repo-scoped skills. Package-local `skills/` directories are included with the package source distribution.

## Principles

- Keep one public repository for the `open_*` series so discovery and stars consolidate.
- Release each tool as its own package and CLI.
- Keep provider roles explicit. For example, `open-gil` uses Kakao Local only for coordinate fallback and TMAP Transit as the route-calculation source of truth.
- Do not commit API keys, raw user prompts, private location logs, or live route-search traces.
- Prefer honest fallback behavior over pretending two map providers will produce the same route.

## Current Commands

```bash
# open-gil
python -m pip install -e "./packages/open-gil[dev]"
PYTHONDONTWRITEBYTECODE=1 python -m pytest packages/open-gil/tests -p no:cacheprovider
python -m build packages/open-gil
```
