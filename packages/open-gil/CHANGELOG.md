# Changelog

## Unreleased

## 0.1.6

- Clarified that `/tmp` virtual environments are only for throwaway checks, and documented a persistent user venv fallback when `pipx` is unavailable.
- Clarified that persistent venv users must run the full open-gil binary path unless they add it to `PATH`.
- Clarified that install-only agent runs should not edit shell startup files, create aliases, or add symlinks.
- Clarified that persistent venv installs should not be deleted during cleanup when the user still needs to run `setup` or use open-gil.
- Clarified that public first-time onboarding should prefer terminal-based installation and API-key setup before agent use.
- Clarified that `open-gil setup` configures only the required TMAP key, and that natural-language agent use is the primary workflow after setup.
- Added Claude Code `/open-gil` onboarding guidance and documented that CLI installation and Claude Code skill registration are separate steps.
- Tightened coordinate fallback guardrails so agents must not approximate coordinates from nearby stations, exits, or address-only search results.

## 0.1.5

- Reworded `open-gil setup` guidance to explain that typed API-key characters are intentionally not shown on screen.

## 0.1.4

- Added `open-gil setup` for first-time users to enter the required TMAP key in the terminal without displaying typed characters.
- Added stronger guidance that API keys should not be pasted into agent chat windows.
- Updated missing-key remediation to prefer `open-gil setup` over passing keys as command arguments.

## 0.1.3

- Clarified that TMAP API key is required while Kakao REST API key is optional.
- Updated setup-status messaging so a missing Kakao key is not presented as a route-planning blocker.

## 0.1.2

- Added `open-gil --version` so agents can verify the installed CLI version before following skill instructions.
- Updated first-run skill instructions to upgrade reused temporary virtual environments instead of accidentally using stale `open-gil` versions.

## 0.1.1

- Added `open-gil config show` and `open-gil config status` to report key setup status without exposing key values.
- Updated agent skill first-run instructions so fresh environments explain the missing TMAP key before route planning.
- Made PyPI/pipx installation the preferred agent setup path and documented temporary venv fallback only for source testing.

## 0.1.0

- Initial MVP CLI package.
- Added TMAP-backed public-transit route planning.
- Added `open-gil config set-key` and `open-gil plan`.
- Added JSON input/output for agent integrations.
- Added in-repository `skills/open-gil` agent instructions.
- Added Kakao Local coordinate fallback for place-name lookup.
- Moved `open-gil` into the `packages/open-gil` monorepo package layout.
- Added fixture/mock tests and optional live TMAP test.
