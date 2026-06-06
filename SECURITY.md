# Security Policy

## Reporting

Please report security issues privately to the project maintainers. Do not open a public issue for secrets exposure, credential handling bugs, or location privacy vulnerabilities.

If this repository has no published security contact yet, create a minimal private advisory in GitHub after the repository is published.

## Sensitive Data

`open-gil` must not store or transmit raw natural-language prompts. TMAP requests should receive only coordinates and route-search times.

Never include API keys, precise private movement history, or raw route-search logs in issues, pull requests, fixtures, or screenshots.

## API Keys

The MVP supports `TMAP_API_KEY` and an opt-in plaintext local config file at `~/.config/open-gil/config.json`. On POSIX systems, the config file is written with `0600` permissions.

