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
- Agent surfaces: Codex repo skill in `.agents/skills/open-gil`, Claude Code project skill in `.claude/skills/open-gil`, package skill in `packages/open-gil/skills/open-gil`
- Output contract: stable JSON envelope plus human-readable Korean route summaries
- Hard guardrail: one TMAP Transit route calculation per natural-language request
- Release status: `open-gil` is published on PyPI

For the design history, tradeoffs, and next steps, see [Open Gil Development Story](docs/open-gil-development-story.md).

## Install

Recommended for most users: install and configure `open-gil` in your own terminal first, then use it from Claude Code, Codex, or another agent.

If you saw open-gil publicly and want Claude Code to set up the repo and skill for you, copy the Korean onboarding prompt in [Open Gil Claude Code Onboarding Prompt](docs/open-gil-claude-code-onboarding-prompt.md).

Agent-assisted installs can be useful for checking a setup, but API-key entry needs a real interactive terminal and some agent shells may not share the same runtime environment as your normal terminal.

```bash
pipx install open-gil
open-gil --version
open-gil setup
open-gil config show
```

Do not paste your TMAP API key into an AI chat. `open-gil setup` asks for the key in your terminal and stores it locally.
`open-gil setup` configures the required TMAP key only. Kakao REST API is optional and can be configured later with `open-gil config set-kakao-key` if you need coordinate fallback.

After setup, the main workflow is to ask Claude Code, Codex, or another agent in natural language:

```text
내일 오후 1시에 올림픽홀 공연이 있는데, 송도에서 몇 시에 출발하면 돼?
```

Claude Code note: installing the CLI does not automatically register the `/open-gil` slash command. To make `/open-gil` available in every Claude Code project, install the skill file once:

```bash
git clone https://github.com/doul735/open_tools.git
mkdir -p "$HOME/.claude/skills/open-gil"
cp open_tools/packages/open-gil/skills/open-gil/SKILL.md "$HOME/.claude/skills/open-gil/SKILL.md"
```

Then restart Claude Code or open a new session. If you open Claude Code from inside this repository, the project skill in `.claude/skills/open-gil` is also available. See the official [Claude Code skills docs](https://docs.claude.com/en/docs/claude-code/skills) for the skill directory format.

If `pipx` is unavailable, use a persistent venv instead of `/tmp`:

```bash
python3 -m venv "$HOME/.local/share/open-gil/venv"
"$HOME/.local/share/open-gil/venv/bin/python" -m pip install --upgrade pip
"$HOME/.local/share/open-gil/venv/bin/python" -m pip install --upgrade "open-gil>=0.1.6"
OPEN_GIL_BIN="$HOME/.local/share/open-gil/venv/bin/open-gil"
"$OPEN_GIL_BIN" --version
```

Use `$OPEN_GIL_BIN` or the full binary path for later commands.
Changing shell startup files, aliases, symlinks, or `PATH` is optional and should be handled as a separate shell setup step.
Do not delete this venv if you plan to run `open-gil setup` or use open-gil later; it is the actual install location for the fallback path.

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
.claude/
  skills/open-gil/
docs/
```

The root `.agents/skills` directory is for Codex repo-scoped skills. The root `.claude/skills` directory is for Claude Code project-scoped skills. Package-local `skills/` directories are included with the package source distribution.

## Principles

- Keep one public repository for the `open_*` series so discovery and stars consolidate.
- Release each tool as its own package and CLI.
- Keep provider roles explicit. For example, `open-gil` uses Kakao Local only for coordinate fallback and TMAP Transit as the route-calculation source of truth.
- Do not commit API keys, raw user prompts, private location logs, or live route-search traces.
- Do not let agents approximate coordinates from nearby stations, exits, or neighborhood points. If exact coordinates are unavailable, ask for Kakao setup, a map link, or user-supplied coordinates.
- Prefer honest fallback behavior over pretending two map providers will produce the same route.

## Current Commands

```bash
# open-gil
python -m pip install -e "./packages/open-gil[dev]"
PYTHONDONTWRITEBYTECODE=1 python -m pytest packages/open-gil/tests -p no:cacheprovider
python -m build packages/open-gil
```
