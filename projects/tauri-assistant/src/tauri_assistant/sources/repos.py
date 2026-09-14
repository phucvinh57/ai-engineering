"""Clone/pull the Tauri docs, API source, and plugins repos."""

from __future__ import annotations

from git import Repo

from tauri_assistant.config import Settings

REPO_URLS = {
    "tauri-docs": "https://github.com/tauri-apps/tauri-docs.git",
    "tauri": "https://github.com/tauri-apps/tauri.git",
    "plugins-workspace": "https://github.com/tauri-apps/plugins-workspace.git",
}

REPO_BRANCHES = {
    "tauri-docs": "v2",
    "tauri": "dev",
    "plugins-workspace": "v2",
}


def sync_repos(settings: Settings, names: list[str] | None = None) -> None:
    """Shallow clone each repo into data/repos/, or pull if present."""
    settings.repos_dir.mkdir(parents=True, exist_ok=True)
    for name in names or list(REPO_URLS):
        dest = settings.repos_dir / name
        if dest.exists():
            Repo(dest).remotes.origin.pull()
        else:
            Repo.clone_from(REPO_URLS[name], dest, branch=REPO_BRANCHES[name], depth=1)
