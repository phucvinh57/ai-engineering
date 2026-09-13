# ai-learning

A monorepo of AI/ML learning projects, managed as a [uv](https://docs.astral.sh/uv/) workspace.

## Structure

Each project lives under `projects/<name>/` as its own uv package with its own `pyproject.toml`. The root `pyproject.toml` only declares the workspace (no root package).

```
projects/
  wayland-assistant/   # RAG chatbot over Wayland protocol & compositor docs
```

## Setup

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then from the repo root:

```bash
uv sync
```

This creates one shared `.venv` for the whole workspace and installs all member projects into it.

## Running a project

Run a project's entry point from the repo root with `--package`:

```bash
uv run --package wayland-assistant wl-assistant
```

Or `cd` into the project directory and run it directly:

```bash
cd projects/wayland-assistant
uv run wl-assistant
```

To run an arbitrary script/module inside a project instead of its console entry point:

```bash
uv run --package wayland-assistant python -m wayland_assistant
```

## Adding a new project

```bash
uv init --package projects/<name>
uv sync
```

It's picked up automatically via the `projects/*` workspace glob in the root `pyproject.toml`.
