# FOV Notification Service

Services that notify satellite operators of upcoming observation schedules and observers of FOV interference alerts.

## Repository layout

- **`services/operator/`** — API for satellite operators to get schedule information with upcoming observations from supported observatories (schedules, status, API key auth). See [services/operator/README.md](services/operator/README.md) for setup, usage, and development.
- **`shared/`** — Shared code (auth, notifications) used by notification services.

## Quick start

From the repository root:

```bash
uv sync --directory services/operator --group dev
uv run --directory services/operator python -m app
```

For full setup, API usage, tests, and tooling, see **[services/operator/README.md](services/operator/README.md)**.
