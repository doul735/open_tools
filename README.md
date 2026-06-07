# open_*

Open-source agent tools that keep LLMs useful without letting them invent operational facts.

This repository is the home for the `open_*` series. Stars, issues, discussions, and project-level documentation live here; each tool is still packaged and released independently so users can install only what they need.

## Packages

| Package | CLI | Status | Purpose |
| --- | --- | --- | --- |
| [`open-gil`](packages/open-gil) | `open-gil` | MVP | TMAP-backed public-transit departure planning for Seoul, Gyeonggi, and Incheon. |
| `open-review` | `open-review` | Planned | Review workflows for code, docs, and release checks. |

## Install

End users should install a specific tool rather than cloning the whole repository.

```bash
pipx install open-gil
```

Developers can work from the monorepo.

```bash
git clone <repository-url>
cd open_gil
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

## Current Commands

```bash
# open-gil
python -m pip install -e "./packages/open-gil[dev]"
PYTHONDONTWRITEBYTECODE=1 python -m pytest packages/open-gil/tests -p no:cacheprovider
python -m build packages/open-gil
```
