from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class HarvestedRepo:
    source_key: str
    commit_hash: str
    source_url: str
    paths: list[str]


class GitHubRepoHarvester:
    def harvest_local_repo(self, repo_root: Path, source_key: str, commit_hash: str) -> HarvestedRepo:
        root = Path(repo_root)
        return HarvestedRepo(
            source_key=source_key,
            commit_hash=commit_hash,
            source_url=_repo_url(source_key),
            paths=_selected_paths(root),
        )


def _selected_paths(root: Path) -> list[str]:
    selected: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        lowered = rel.casefold()
        if any(blocked in lowered for blocked in ["secret", "token", "password", "credential"]):
            continue
        name = path.name.casefold()
        is_readme = name == "readme" or name.startswith("readme.")
        is_license = name == "license" or name.startswith("license.")
        if is_readme or is_license or rel.startswith(("docs/", "examples/", "src/", "tests/")):
            selected.append(rel)
    return selected


def _repo_url(source_key: str) -> str:
    if source_key == "janestreet_ppx_expect":
        return "https://github.com/janestreet/ppx_expect"
    return f"https://github.com/{source_key.replace('_', '/')}"
