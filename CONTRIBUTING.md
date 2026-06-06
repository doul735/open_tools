# Contributing

Thanks for helping improve `open-gil`.

## Local Setup

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

Run the default test suite:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider
```

Default tests use fixtures and mocks. They must pass without `TMAP_API_KEY`.

## Live TMAP Tests

Live tests are optional and run only when `TMAP_API_KEY` is set.

```bash
export TMAP_API_KEY="your_app_key"
PYTHONDONTWRITEBYTECODE=1 python -m pytest tests/test_live_tmap.py -p no:cacheprovider
```

Do not commit API keys, raw user prompts, or private route-search logs.

## Pull Requests

Keep changes focused. For route behavior changes, include fixture tests and explain whether live TMAP verification was run.

