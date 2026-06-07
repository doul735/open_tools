# Contributing

Thanks for helping improve the `open_*` tool series.

## Local Setup

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e "./packages/open-gil[dev]"
```

Run the default test suite:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest packages/open-gil/tests -p no:cacheprovider
```

Default tests use fixtures and mocks. They must pass without `TMAP_API_KEY`.

## Live TMAP Tests

Live tests are optional and run only when `TMAP_API_KEY` is set.

```bash
export TMAP_API_KEY="your_app_key"
PYTHONDONTWRITEBYTECODE=1 python -m pytest packages/open-gil/tests/test_live_tmap.py -p no:cacheprovider
```

Kakao Local live checks are optional and require `KAKAO_REST_API_KEY`.

Do not commit API keys, raw user prompts, private route-search logs, or precise private movement histories.

## Pull Requests

Keep changes focused. For route behavior changes, include fixture tests and explain whether live TMAP/Kakao verification was run.
