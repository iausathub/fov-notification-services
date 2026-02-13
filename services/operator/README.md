# FOV Notification Service (Operator)

A service that notifies satellite operators of upcoming observation schedules.

## Usage

To get a specific observatory's schedule, make a GET request to `/schedule/{observatory_name}`.

- Example: http://127.0.0.1:8000/schedule/rubin

To get the full schedule for all observatories, make a GET request to `/schedule`.

- Example: http://127.0.0.1:8000/schedule

API key is required for all requests. Provide it in the `X-API-Key` header. Keys are manually generated for now.

## Setup

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### Local Development Setup

#### 1. Install dependencies

From the **repository root**:

```bash
uv sync --directory services/operator --group dev
```

Or from **this directory** (`services/operator`):
```bash
uv sync --group dev
```

This also installs the `shared` package (auth, notifications) as an editable dependency. If you change dependencies in `shared/pyproject.toml`, run:

```bash
uv sync --directory shared --group dev
# then re-sync the operator service
uv sync --directory services/operator --group dev
```

#### 2. Set up pre-commit hooks (optional)

From the repository root:

```bash
pre-commit install
```

This enables automatic formatting and linting on each commit (black, ruff, towncrier).

#### 3. Run the application

From the **repository root**:

```bash
uv run --directory services/operator python -m app
```

From **this directory**:

```bash
uv run python -m app
```

Server runs at http://127.0.0.1:8000 (docs at http://127.0.0.1:8000/docs).

## Development

### Tools

| Tool       | Purpose                        |
| ---------- | ------------------------------ |
| black      | Code formatting                |
| ruff       | Linting                        |
| pre-commit | Git hooks for code quality     |
| towncrier  | Changelog management           |

### Format and lint

From this directory:

```bash
black .
ruff check .
ruff check --fix .
```

From the repository root:

```bash
uv run --directory services/operator black .
uv run --directory services/operator ruff check .
uv run --directory services/operator ruff check --fix .
```

### Tests

From this directory:

```bash
uv run pytest -v
```

From the repository root:

```bash
uv run --directory services/operator pytest -v
```

Set `TEST_DATABASE_URL` if needed (e.g. for a local Postgres). Use the interpreter at `services/operator/.venv/bin/python` in your IDE so imports (e.g. `auth`) resolve.

### Pre-commit on all files

```bash
pre-commit run --all-files
```
