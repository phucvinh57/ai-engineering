from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from git import Repo
from loguru import logger

REPOS_DIR = Path(__file__).parent.parent.parent.parent / "data" / "repos"
REPO_BASE_URI = "git@github.com:tauri-apps"
REPO_LIST = ["tauri-docs", "tauri", "plugins-workspace"]

REPO_BRANCHES = {
    "tauri-docs": "v2",
    "tauri": "dev",
    "plugins-workspace": "v2",
}


def sync_repo(name: str, branch: str) -> None:
    repo_dir = REPOS_DIR / name
    if repo_dir.exists():
        logger.info(f"Pulling latest changes for {name}")
        Repo(repo_dir).remotes.origin.pull()
    else:
        repo_uri = f"{REPO_BASE_URI}/{name}.git"
        logger.info(f"Cloning {name} from {repo_uri}")
        Repo.clone_from(repo_uri, repo_dir, branch=branch, depth=1)


def sync_repos() -> None:
    REPOS_DIR.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=len(REPO_LIST)) as executor:
        futures = [executor.submit(sync_repo, repo_name, REPO_BRANCHES[repo_name]) for repo_name in REPO_LIST]
        for future in futures:
            future.result()
