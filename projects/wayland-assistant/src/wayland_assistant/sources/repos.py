"""Clone/pull the protocol repos and enumerate their XML files by tier."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from git import Repo

from wayland_assistant.config import Settings

REPO_URLS = {
    "wayland": "https://gitlab.freedesktop.org/wayland/wayland.git",
    "wayland-protocols": "https://gitlab.freedesktop.org/wayland/wayland-protocols.git",
    "wlr-protocols": "https://gitlab.freedesktop.org/wlroots/wlr-protocols.git",
}

GITLAB_PROJECT_PATH = {
    "wayland": "wayland/wayland",
    "wayland-protocols": "wayland/wayland-protocols",
    "wlr-protocols": "wlroots/wlr-protocols",
}

# maturity -> (repo, relative glob dir), core is a single file handled separately
TIER_1_DIRS = [
    ("stable", "wayland-protocols", "stable"),
    ("staging", "wayland-protocols", "staging"),
    ("wlr", "wlr-protocols", "unstable"),
]
TIER_2_DIRS = [
    ("unstable", "wayland-protocols", "unstable"),
    ("experimental", "wayland-protocols", "experimental"),
]


@dataclass(frozen=True)
class ProtocolFile:
    path: Path
    maturity: str
    repo: str


def sync_repos(settings: Settings) -> None:
    """Shallow clone each protocol repo into data/repos/, or pull if present."""
    settings.repos_dir.mkdir(parents=True, exist_ok=True)
    for name, url in REPO_URLS.items():
        dest = settings.repos_dir / name
        if dest.exists():
            Repo(dest).remotes.origin.pull()
        else:
            Repo.clone_from(url, dest, depth=1)


def list_protocol_files(settings: Settings, tier: int = 1) -> list[ProtocolFile]:
    """List XML protocol files for the given tier (1, or 2 which includes tier 1)."""
    files: list[ProtocolFile] = []

    core_xml = settings.repos_dir / "wayland" / "protocol" / "wayland.xml"
    if core_xml.exists():
        files.append(ProtocolFile(path=core_xml, maturity="core", repo="wayland"))

    dirs = list(TIER_1_DIRS)
    if tier >= 2:
        dirs += TIER_2_DIRS

    for maturity, repo, subdir in dirs:
        base = settings.repos_dir / repo / subdir
        if not base.exists():
            continue
        for xml_path in sorted(base.rglob("*.xml")):
            files.append(ProtocolFile(path=xml_path, maturity=maturity, repo=repo))

    return files


def blob_url(settings: Settings, pf: ProtocolFile) -> str:
    """Canonical gitlab.freedesktop.org blob URL for a protocol XML file."""
    repo_dir = settings.repos_dir / pf.repo
    branch = Repo(repo_dir).active_branch.name
    rel_path = pf.path.relative_to(repo_dir)
    project_path = GITLAB_PROJECT_PATH[pf.repo]
    return f"https://gitlab.freedesktop.org/{project_path}/-/blob/{branch}/{rel_path}"
